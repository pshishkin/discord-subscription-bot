from operator import index
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column, BigInteger, Numeric, String, ForeignKey, DateTime
import enum
from sqlalchemy import Enum
from sqlalchemy.sql import func


class UserState(enum.Enum):
    expired = 1
    disabled = 2
    to_be_disabled = 3
    active = 4

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = Column(BigInteger, primary_key=True)
    name = Column(String)
    display_name = Column(String)
    state = Column(Enum(UserState), default=UserState.expired)
    balance_dev = Column(Numeric(10, 2), default=0)
    active_subscription_start_ts = Column(DateTime)
    updates = relationship("ScheduledUserUpdate", back_populates="user")
    charges = relationship("Charge", back_populates="user")
    expired_status_started = Column(DateTime, nullable=False)

    def __repr__(self):
        return "<User(id='%d', name='%s')>" % (self.id, self.name)

    def load_balance(self):
        self.balance = self.balance_dev

class Charge(Base):
    __tablename__ = 'charges'

    id = Column(BigInteger, primary_key=True)
    amount = Column(Numeric(10, 2), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    paid_from = Column(DateTime, nullable=False)
    paid_till = Column(DateTime, nullable=False)
    user_id = Column(BigInteger, ForeignKey('users.id'))
    user = relationship("User", back_populates="charges")


class ScheduledUserUpdate(Base):
    __tablename__ = 'scheduled_user_updates'

    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.id'))
    user = relationship("User", back_populates="updates")
    update_time = Column(DateTime, nullable=False, index=True)

    def __repr__(self):
        return f'<ScheduledUserUpdate()>'

