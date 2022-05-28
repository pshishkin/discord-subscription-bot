from sqlalchemy import create_engine
import logging
from sqlalchemy.orm import sessionmaker
from bot_data_model import Base
from sqlalchemy.orm import Session


# session = Session()

# id = 1234
# user = session.get(User, id)
# if user:
#     print(user)
# else:
#     ed_user = User(id=id, name="Pasha")
#     session.add(ed_user)
# session.commit()

def connect_to_db(db_conn_string, logging_level) -> Session:
    logging.getLogger('sqlalchemy.engine').setLevel(logging_level)
    engine = create_engine(db_conn_string)

    # check that connection was successful
    engine.connect()

    Base.metadata.create_all(engine, checkfirst=True)
    Session = sessionmaker(bind=engine)

    return Session