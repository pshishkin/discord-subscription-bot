from bot_data_model import User, UserState, Charge, ScheduledUserUpdate
import enum
from decimal import *


class BalanceType(enum.Enum):
    CRYPTO = 2
    DB_STORAGE = 3


class Crypto:

    def __init__(self, config):
        self.balance_type = config['balance']

    def init_balance(self, user: User):
        if self.balance_type == BalanceType.DB_STORAGE:
            user.balance = user.balance_dev
        else:
            pass
            # TODO add crypto read here
    
    def sub_balance(self, user: User, balance_delta: Decimal, sess) -> bool:
        if self.balance_type == BalanceType.DB_STORAGE:
            user.balance_dev -= balance_delta
            user.balance = user.balance_dev
            sess.add(user)
            return True
        else:
            pass
            # TODO add crypto read here        

    def set_balance(self, user: User, new_balance: Decimal, sess) -> bool:
        if self.balance_type == BalanceType.DB_STORAGE:
            user.balance = user.balance_dev = new_balance
            sess.add(user)
            return True
        else:
            return False


