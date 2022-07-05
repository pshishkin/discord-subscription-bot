import discord
from discord.ext import commands
from discord import Client
from discord.ext.commands import Context
from bot_data_model import User, UserState, Charge, ScheduledUserUpdate
from sqlalchemy.orm import Session
from datetime import datetime as dt
from datetime import timedelta as td
import asyncio
from typing import Any
import logging
from discord.ext import tasks, commands
from crypto import Crypto
import traceback
import sys


class SubscriptionBot(commands.Bot):


    def __init__(
            self, 
            command_prefix, 
            guild, 
            crypto: Crypto, 
            subscription_period,
            updates_frequency, 
            subscription_fee,
            subscription_roles_names, 
            info_channel_name,
            Session: Session,
            *args, **kwargs):
        
        super(SubscriptionBot, self).__init__(command_prefix, *args, **kwargs)
        self._logger = logging.getLogger('subscription_bot.bot')
        
        self._GUILD = guild
        self._crypto = crypto
        assert(subscription_period in ['minute', 'month'])
        self._subscription_period = subscription_period
        self._updates_frequency = updates_frequency
        self._subscription_fee = subscription_fee
        self._subscription_roles_names = subscription_roles_names
        self._info_channel_name = info_channel_name
        self._Session = Session

        self.on_ready_finished = False
        

    async def on_ready(self):
        self._guild = discord.utils.get(self.guilds, name=self._GUILD)

        if not self._guild:
            raise Exception(f"Can't find guild {self._GUILD} in list of guilds: [{self.guilds}]")
        self._logger.warn(
            f'{self.user} is connected to the following guild: '
            f'{self._guild.name}(id: {self._guild.id})'
        )

        if not self._subscription_roles_names:
            raise Exception(f"Specify at least one Role that will be assigned after user subscription")

        self._subscription_roles = []
        for srn in self._subscription_roles_names:
            subscription_role = discord.utils.get(self._guild.roles, name=srn)
            if not subscription_role:
                raise Exception(f"Can't find role {srn} in roles list: [{self._guild.roles}]")
            else:
                self._subscription_roles.append(subscription_role)
        self._logger.warn(
            f'Using the following roles: {self._subscription_roles}'
        )

        all_channels = await self._guild.fetch_channels()
        info_channels = [x for x in all_channels if x.name == self._info_channel_name]
        if len(info_channels) == 0:
            raise Exception(f"Can't find channel {self._info_channel_name} in guild channels: [{all_channels}]")
        if len(info_channels) >= 2:
            raise Exception(f"Channel name {self._info_channel_name} is ambigious — found more than one channel with such a name. Consider another channel name.")
        self._info_channel = info_channels[0]
        
        self._logger.warn(f'Using the following info-channel: {self._info_channel}')

        self.on_ready_finished = True
        

    def get_active_subscription_end(self, sess: Session, now: dt, user: User):
        active_subscription_charge = sess.query(Charge).filter(Charge.user_id == user.id, Charge.timestamp <= now, Charge.paid_till > now).first()
        if active_subscription_charge:
            return active_subscription_charge.paid_till
        else:
            return None

    def is_any_subscription(self, sess: Session, user: User) -> bool:
        subscription_count = sess.query(Charge).filter(Charge.user_id == user.id).count()
        if subscription_count:
            return True
        else:
            return False

    async def get_user_and_lock(self, sess: Session, ctx: Context) -> User:
        # user = sess.query(User).filter(User.id == ctx.author.id).with_for_update().first()
        user = sess.query(User).filter(User.id == ctx.author.id).first()
        if not user:
            user = User(id=ctx.author.id, expired_status_started=dt.now())
            self._crypto.write_keypair_to_user(user)
            sess.add(user)
            sess.commit()
            # user = sess.query(User).filter(User.id == ctx.author.id).with_for_update().first()
            user = sess.query(User).filter(User.id == ctx.author.id).first()
        user.display_name = ctx.author.display_name
        user.name = ctx.author.name

        sess.add(user)

        await self._crypto.init_balance(user)

        return user

    async def lock_user(self, sess: Session, ext_user: User) -> User:
        # user = sess.query(User).filter(User.id == ext_user.id).with_for_update().first()
        user = sess.query(User).filter(User.id == ext_user.id).first()

        sess.add(user)

        await self._crypto.init_balance(user)

        return user


    async def update_user_state(self, sess: Session, user: User, from_command=True):
        # from_command is used to understand whether to inform user or not
        now = dt.now()
        active_subscription_end = self.get_active_subscription_end(sess, now, user)

        if user.state == UserState.active:
            if not active_subscription_end:
                period_start, period_end = self._get_active_billing_period(user.active_subscription_start_ts, now)
                if user.balance >= self._subscription_fee and await self.charge_user(sess, user, now, period_start, period_end):
                    await self._on_user_subscription_prolonged(user, from_command)
                    #keep user.state = UserState.active
                else:
                    user.state = UserState.expired
                    user.active_subscription_start_ts = None
                    user.expired_status_started = dt.now()
                    await self._on_user_unsubscribed(user, from_command)

        elif user.state == UserState.to_be_disabled:
            if not active_subscription_end:
                user.state = UserState.disabled
                user.active_subscription_start_ts = None
                await self._on_user_unsubscribed(user, from_command)
        
        elif user.state == UserState.expired and user.balance >= self._subscription_fee:
            if await self.charge_user(sess, user, now, now, self._get_billing_period_end(now)):
                user.state = UserState.active
                user.active_subscription_start_ts = now
                await self._on_user_subscribed(user, from_command)

        sess.add(user)


    async def charge_user(self, sess: Session, user: User, now: dt, period_start: dt, period_end: dt) -> bool:
        now = dt.now()
        await self._on_user_charge_attempt(user)
        tx_hash = await self._crypto.sub_balance(user, self._subscription_fee, sess)
        if tx_hash:
            self._logger.info(f'User {user.display_name} was CHARGED for {self._subscription_fee}, tx: {tx_hash}')
            sess.add(user)
            charge = Charge(
                amount=self._subscription_fee, 
                user_id=user.id, 
                timestamp=now, 
                paid_from=period_start,
                paid_till=period_end,
                tx_hash=tx_hash)
            sess.add(charge)
            await self._on_user_charge_success(user)
            return True
        else:
            self._logger.info(f'CANT CHARGE user {user.display_name} was for {self._subscription_fee}')
            await self._on_user_charge_failure(user)
            return False
    
    async def _on_user_subscribed(self, user: User, from_command: bool):
        member = await self._guild.fetch_member(user.id)
        self._logger.info(f"adding roles [{self._subscription_roles}] to user {member}")
        await member.add_roles(*self._subscription_roles)
        await self._info_channel.send(f'User {user.name} is now subscribed')
        if from_command == False:
            res = await member.send(f"""You're now subscribed to "{self._guild.name}". Congrats! """)

    async def _on_user_subscription_prolonged(self, user: User, from_command: bool):
        member = await self._guild.fetch_member(user.id)
        await self._info_channel.send(f'User {user.name} subsription is prolonged')
        if from_command == False:
            res = await member.send(f"""Your subscription to "{self._guild.name}" was prolonged, thank's for staying with us!""")

    async def _on_user_unsubscribed(self, user: User, from_command: bool):
        member = await self._guild.fetch_member(user.id)
        self._logger.info(f"removing roles [{self._subscription_roles}] from user {member}")
        await member.remove_roles(*self._subscription_roles)
        await self._info_channel.send(f'User {user.name} is now unsubscribed')
        if from_command == False:
            res = await member.send(f"""Your subscription to "{self._guild.name}" was cancelled due to insufficcient funds.""")

    async def _on_user_charge_attempt(self, user: User):
        await self._info_channel.send(f'Trying to charge {user.name}')

    async def _on_user_charge_success(self, user: User):
        await self._info_channel.send(f'Successfully charged {user.name}')

    async def _on_user_charge_failure(self, user: User):
        await self._info_channel.send(f'Failed to charge {user.name}')

    def _get_billing_period_end(self, period_start) -> dt:
        if self._subscription_period == 'minute':
            return period_start + td(minutes=1)
        elif self._subscription_period == 'month':
            period_end = period_start + td(days=25)
            while True:
                if period_end.day == period_start.day:
                    break
                next_period_end = period_end + td(days=1)
                months_diff = next_period_end.month - period_start.month + (next_period_end.year - period_start.year) * 12
                if months_diff >= 2:
                    break
                period_end = next_period_end
            return period_end
        raise Exception(f"Wrong time period is being used for billing period: {self._subscription_period}")


    def _get_active_billing_period(self, first_period_start, ts_should_be_in_period):
        if first_period_start > ts_should_be_in_period:
            raise Exception("You shall not query billing period to the past from the first_period_start")
        period_start = first_period_start
        period_end = self._get_billing_period_end(period_start)
        while ts_should_be_in_period > period_end:
            period_start = period_end
            period_end = self._get_billing_period_end(period_start)
        return (period_start, period_end)


    def refresh_all_user_updates(self, sess: Session):
        for user in sess.query(User).all():
            self.refresh_user_updates(sess, user)


    def refresh_user_updates(self, sess: Session, user: User):
        sess.query(ScheduledUserUpdate).filter(User.id == user.id).delete(synchronize_session=False)
        if user.state == UserState.active or user.state == UserState.to_be_disabled:
            last_charge = sess.query(Charge).filter(Charge.user_id == user.id).order_by(Charge.paid_till.desc()).first()
            if last_charge:
                update = ScheduledUserUpdate(user=user, update_time=last_charge.paid_till)
                sess.add(update)
        elif user.state == UserState.expired:
            user.expired_status_started
            for update_window, update_frequency in self._updates_frequency:
                now = dt.now()
                if now < user.expired_status_started + update_window:
                    next_update = user.expired_status_started
                    safe_cnt = 1000
                    while next_update < now and safe_cnt > 0:
                        next_update += update_frequency
                        safe_cnt -= 1
                    if next_update >= now:
                        update = ScheduledUserUpdate(user=user, update_time=next_update)
                        sess.add(update)
                    else:
                        self._logger.error("couldn't calculate next update time due to infinite loop")
                    # break to make only one first update
                    break


def create_bot(guild, Session: Session, crypto: Crypto, launch_config):
    bot = SubscriptionBot(
        '$', 
        guild, 
        crypto, 
        launch_config['subscription_period'], 
        launch_config['updates_frequency'], 
        launch_config['subscription_fee'], 
        launch_config['roles'],
        launch_config['info_channel_name'],
        Session)
    

    with Session() as sess:
        bot.refresh_all_user_updates(sess)
        sess.commit()

    updater = ScheduledUpdater(bot, Session)

    @bot.command(name='subscribe', help='Shows you how to subscribe')
    async def subscribe(ctx: Context):
        with Session() as sess:
            user = await bot.get_user_and_lock(sess, ctx)
            await bot.update_user_state(sess, user)

            if user.state == UserState.disabled:
                user.state = UserState.expired
                sess.add(user)
                await bot.update_user_state(sess, user)
                # it could become here either expired or active

            if user.state == UserState.active:
                msg = f"You're subscribed. Next billing date is {bot.get_active_subscription_end(sess, dt.now(), user)}."
                if user.balance > 0:
                    msg += f'\n{user.balance} is your current account balance.'
            
            elif user.state == UserState.expired:
                balance_shortage = bot._subscription_fee - user.balance
                msg = f"Top up your balance for at least {balance_shortage} {bot._crypto.token_name} to start subscription."
                msg += f'\nTransfer {bot._crypto.token_name} to {user.keypair.public_key} (Solana network).'
                if user.balance > 0:
                    msg += f'\nYou already have {user.balance} {bot._crypto.token_name} on your account.'
            
            elif user.state == UserState.to_be_disabled:
                user.state = UserState.active
                sess.add(user)
                msg = f"Your subscription is turned back. Next billing date is {bot.get_active_subscription_end(sess, dt.now(), user)}."
            
            if user.state == UserState.expired:
                user.expired_status_started = dt.now()
                sess.add(user)

            bot.refresh_user_updates(sess, user)
            sess.commit()
            await ctx.send(msg)


    @bot.command(name='status', help='Shows you your subscription status and account balance')
    async def status(ctx):

        # puser = await bot.get_user(972907979001200661)
        # await bot.send_message(puser, "Your message goes here")

        with Session() as sess:
            user = await bot.get_user_and_lock(sess, ctx)
            await bot.update_user_state(sess, user)
            if user.state == UserState.expired:
                user.expired_status_started = dt.now()
                sess.add(user)
            bot.refresh_user_updates(sess, user)
            sess.commit()

            if user.state == UserState.disabled:
                msg = f'Your subscription is cancelled.'
                if user.balance > 0:
                    msg += f'\n{user.balance} {bot._crypto.token_name} is your current account balance.'
            
            elif user.state == UserState.active:
                msg = f"You're subscribed. Next billing date is {bot.get_active_subscription_end(sess, dt.now(), user)}."
                if user.balance > 0:
                    msg += f'\n{user.balance} {bot._crypto.token_name} is your current account balance.'
            
            elif user.state == UserState.expired:
                balance_shortage = bot._subscription_fee - user.balance
                if bot.is_any_subscription(sess, user):
                    msg = f"Your subscription has expired. Top up your balance for at least {balance_shortage} {bot._crypto.token_name} to start subscription."
                    msg += f'\nTransfer {bot._crypto.token_name} to {user.keypair.public_key} (Solana network).'
                    if user.balance > 0:
                        msg += f'\nYou already have {user.balance} {bot._crypto.token_name} on your account.'
                else:
                    msg = f"You're not susbscribed yet. Top up your balance for at least ${balance_shortage} to start subscription."
                    msg += f'\nTransfer {bot._crypto.token_name} to {user.keypair.public_key} (Solana network).'
                    if user.balance > 0:
                        msg += f'\nYou already have {user.balance} {bot._crypto.token_name} on your account.'


            elif user.state == UserState.to_be_disabled:
                msg = f"Your subsription is due to be cancelled after {bot.get_active_subscription_end(sess, dt.now(), user)}."

            await ctx.send(msg)

    @bot.command(name='unsubscribe', help='Unsubscribes you')
    async def unsubscribe(ctx):
        with Session() as sess:
            user = await bot.get_user_and_lock(sess, ctx)
            await bot.update_user_state(sess, user)

            if user.state == UserState.disabled:
                msg = f'Your subscription is already disabled.'
            
            elif user.state == UserState.active:
                user.state = UserState.to_be_disabled
                msg = f"Got you, your subsription is due to be cancelled after {bot.get_active_subscription_end(sess, dt.now(), user)}."
            
            elif user.state == UserState.expired:
                balance_shortage = bot._subscription_fee - user.balance
                msg = f"Got you, you're unsubscribed."

            elif user.state == UserState.to_be_disabled:
                msg = f"Your subsription is due to be cancelled after {bot.get_active_subscription_end(sess, dt.now(), user)}."

            bot.refresh_user_updates(sess, user)
            sess.commit()
            await ctx.send(msg)
            
    @bot.command(name='setbalance')
    async def setbalance(ctx, new_balance: int):
        with Session() as sess:
            user = await bot.get_user_and_lock(sess, ctx)
            if bot._crypto.set_balance(user, new_balance, sess):
                sess.commit()
                await ctx.send(f'Your balance now is {user.balance}')
            else:
                await ctx.send(f'You can change balance only in dev mode. Please fill your real crypto balance instead.')
            
    return bot


class ScheduledUpdater(commands.Cog):
    def __init__(self, bot: SubscriptionBot, Session: Session):
        self.index = 0
        self.bot = bot
        self._logger = logging.getLogger('subscription_bot.updater')
        self._Session = Session
        self.updater.start()

    def cog_unload(self):
        self.updater.cancel()

    @tasks.loop(seconds=5.0)
    async def updater(self):
        self.index += 1
        self._logger.info(f'updater iteration {self.index}')
        if not self.bot.on_ready_finished:
            self._logger.info(f'skip updater iteration {self.index} because bot.on_ready_finished is False')
            return
        
        try:
            with self._Session() as sess:
                for update in sess.query(ScheduledUserUpdate).filter(ScheduledUserUpdate.update_time <= dt.now()):
                    self._logger.info(f'scheduled update for user {update.user.name}')
                    # save here to avoid losing update after deletion 
                    # (i'm not sure whether it will be dropped from the python representation as well)
                    user = await self.bot.lock_user(sess, update.user)
                    await self.bot.update_user_state(sess, user, from_command=False)
                    self.bot.refresh_user_updates(sess, user)
                    sess.commit()
        except Exception:
            self._logger.error('Exception in background user updater')
            traceback.print_exception(*sys.exc_info())

    @updater.before_loop
    async def before_printer(self):
        self._logger.info('starting updater...')
        await self.bot.wait_until_ready()
