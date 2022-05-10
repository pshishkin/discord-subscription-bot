from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, BigInteger, String

Base = declarative_base()

class User(Base):
     __tablename__ = 'users'

     id = Column(BigInteger, primary_key=True)
     name = Column(String)
     display_name = Column(String)

     def __repr__(self):
        return "<User(id='%d', name='%s')>" % (self.id, self.name)

