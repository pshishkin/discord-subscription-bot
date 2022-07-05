import logging
from bot_data_model import User, UserState, Charge, ScheduledUserUpdate
import enum
import json
from decimal import *

import solana.system_program as sp
from solana.publickey import PublicKey
from solana.keypair import Keypair
from solana.rpc.api import Client
from solana.rpc.async_api import AsyncClient
from solana.transaction import Transaction, TransactionInstruction, AccountMeta
from spl.token.async_client import AsyncToken
from spl.token.constants import TOKEN_PROGRAM_ID
from solana.rpc.types import TxOpts

from solana.transaction import Transaction, TransactionInstruction
from spl.token.instructions import (
    initialize_mint,
    InitializeMintParams,
    initialize_account,
    InitializeAccountParams,
    mint_to_checked,
    MintToCheckedParams,
    get_associated_token_address,
    create_associated_token_account,
    transfer_checked,
    TransferCheckedParams,
)


class BalanceType(enum.Enum):
    CRYPTO = 2
    DB_STORAGE = 3


class Crypto:

    def __init__(self, config, payer_secret_key_str, crypto_recipients_str):
        self.balance_type = config['balance']
        self.token_name = config['token_name']
        self.token_address = config['token_address']
        self.decimals = config['decimals']
        self.solana_url = config['solana_url']
        self.fee_payer_keypair: Keypair = Keypair.from_secret_key(bytes(json.loads(payer_secret_key_str)))
        self._logger = logging.getLogger('subscription_bot.crypto')

        recipients = dict(json.loads(crypto_recipients_str))
        if sum(list(recipients.values())) != 100:
            raise Exception("Sum of recepient shares doesn't equal to 100%, which should be")
        self._recipients = [(PublicKey(k), Decimal(v)/100) for k, v in recipients.items()]
        
        self.solana_cli = AsyncClient(self.solana_url)
        self.token = AsyncToken(self.solana_cli, PublicKey(self.token_address), PublicKey(TOKEN_PROGRAM_ID), self.fee_payer_keypair)

    def write_keypair_to_user(self, user: User):
        kp = Keypair.generate()
        user.secret_key_json = json.dumps([int(b) for b in kp.secret_key])
        user._load_key()

    async def _get_token_balance(self, kp: Keypair) -> Decimal:
        ans = await self.token.get_accounts(kp.public_key)
        self._logger.info(f'Response from Solana get_accounts:\n{ans}')
        if 'result' not in ans or 'value' not in ans['result']:
            raise Exception('Incorrect answer while fetching token balance from Solana')
        value = ans['result']['value']
        if not value:
            return Decimal(0)
        for val in value:
            info = val['account']['data']['parsed']['info']
            if info['mint'] == self.token_address:
                balance = Decimal(info['tokenAmount']['amount']) / (Decimal(10) ** info['tokenAmount']['decimals'])
                return balance
        raise Exception("Can't find token in response from Solana")

    async def init_balance(self, user: User):
        if self.balance_type == BalanceType.DB_STORAGE:
            user.balance = user.balance_dev
        else:
            user.balance = await self._get_token_balance(user.keypair)

    async def _charge_token(self, kp_from: Keypair, balance_delta: Decimal) -> str:
        txn = Transaction(fee_payer=self.fee_payer_keypair.public_key)

        for recipient_public_key, share in self._recipients:
            self._logger.info(f'Adding to transaction:')
            self._logger.info(f'Adding to transaction: program_id={TOKEN_PROGRAM_ID}')
            self._logger.info(f'Adding to transaction: source={get_associated_token_address(kp_from.public_key, self.token.pubkey)}')
            self._logger.info(f'Adding to transaction: mint={self.token.pubkey}')
            self._logger.info(f'DBG: dest_associated_owner={recipient_public_key}')
            self._logger.info(f'Adding to transaction: dest={get_associated_token_address(recipient_public_key, self.token.pubkey)}')
            self._logger.info(f'Adding to transaction: owner={kp_from.public_key}')
            self._logger.info(f'Adding to transaction: amount={int(balance_delta * (10 ** self.decimals) * share)}')
            self._logger.info(f'Adding to transaction: decimals={self.decimals}')

            txn.add(
                transfer_checked(
                    TransferCheckedParams(
                        program_id=TOKEN_PROGRAM_ID,
                        source=get_associated_token_address(kp_from.public_key, self.token.pubkey),
                        mint=self.token.pubkey,
                        dest=get_associated_token_address(recipient_public_key, self.token.pubkey),
                        owner=kp_from.public_key,
                        amount=int(balance_delta * (10 ** self.decimals) * share),
                        decimals=self.decimals
                    )
                )
            )

        signers = [self.fee_payer_keypair, kp_from]
        ans = await self.solana_cli.send_transaction(txn, *signers)

        return ans.get('result', None)

    def sub_balance(self, user: User, balance_delta: Decimal, sess) -> str:
        if self.balance_type == BalanceType.DB_STORAGE:
            user.balance_dev -= balance_delta
            user.balance = user.balance_dev
            sess.add(user)
            return True
        else:
            tx_hash = self._charge_token(user.keypair, balance_delta)
            if tx_hash:
                user.balance -= balance_delta
                return tx_hash
            else:
                return None

    def set_balance(self, user: User, new_balance: Decimal, sess) -> bool:
        if self.balance_type == BalanceType.DB_STORAGE:
            user.balance = user.balance_dev = new_balance
            sess.add(user)
            return True
        else:
            return False


