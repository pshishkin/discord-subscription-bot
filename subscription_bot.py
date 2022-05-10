import discord
from discord.ext import commands
from discord.ext.commands import Context
from bot_user import User
from sqlalchemy.orm import Session

class SubscriptionBot(commands.Bot):

    def __init__(self, command_prefix, guild, Session: Session, *args, **kwargs):
        super(SubscriptionBot, self).__init__(command_prefix, *args, **kwargs)
        self._GUILD = guild
        self._Session = Session

    async def on_ready(self):
        guild = discord.utils.get(self.guilds, name=self._GUILD)

        assert(guild)

        print(
            f'{self.user} is connected to the following guild:\n'
            f'{guild.name}(id: {guild.id})'
        )
    
    def get_or_create_user(self, sess: Session, ctx: Context) -> User:
        user = sess.get(User, ctx.author.id)
        if not user:
            user = User(id=ctx.author.id)
        user.display_name = ctx.author.display_name
        user.name = ctx.author.name

        sess.add(user)

        return user

    # async def on_message(self, message):
    #     if message.author == self.user:
    #         return
        
    #     print(message)
    #     print(message.mentions)

    #     response = f'''You've said {message.content}'''
    #     await message.channel.send(response)
    
def create_bot(guild, Session: Session):
    bot = SubscriptionBot('$', guild, Session)

    @bot.command(name='subscribe', help='Showes you how to subscribe')
    async def subscribe(ctx: Context):
        with Session() as sess:
            user = bot.get_or_create_user(sess, ctx)
            await ctx.send('subscription request')
            sess.commit()

    @bot.command(name='status', help='Shows you your subscription status and account balance')
    async def status(ctx):
        with Session() as sess:
            user = bot.get_or_create_user(sess, ctx)
            await ctx.send('status request')
            sess.commit()

    @bot.command(name='unsubscribe', help='Unsubscribes you')
    async def unsubscribe(ctx):
        with Session() as sess:
            user = bot.get_or_create_user(sess, ctx)
            await ctx.send('unsubscribe request')
            sess.commit()

    return bot

