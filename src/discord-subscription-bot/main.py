import os
import logging
import discord
from dotenv import load_dotenv
from launch_config import LAUNCH_CONFIG_OPTIONS

from subscription_bot import ScheduledUpdater, create_bot
from dbmananaging import connect_to_db
from crypto import Crypto

if __name__ == '__main__':
    load_dotenv()
    TOKEN = os.getenv('DISCORD_TOKEN')
    GUILD = os.getenv('DISCORD_GUILD')
    DB_CONN_STRING = os.getenv('DB_CONN_STRING')
    LAUNCH_MODE = os.getenv('LAUNCH_MODE')
    SOLANA_FEE_PAYER_SECRET_KEY_STR = os.getenv('SOLANA_FEE_PAYER_SECRET_KEY_STR')
    CRYPTO_RECIPIENTS_STR = os.getenv('CRYPTO_RECIPIENTS_STR')
    LAUNCH_CONFIG = LAUNCH_CONFIG_OPTIONS[LAUNCH_MODE]
    LOGGING_LEVEL = LAUNCH_CONFIG['logging_level']

    # FORMAT = '%(asctime)s %(message)s'
    # logging.basicConfig(level=logging.INFO, format=FORMAT)
    logging.basicConfig(level=logging.INFO)
    Session = connect_to_db(DB_CONN_STRING, LOGGING_LEVEL)
    crypto = Crypto(LAUNCH_CONFIG['crypto'], SOLANA_FEE_PAYER_SECRET_KEY_STR, CRYPTO_RECIPIENTS_STR)
    bot = create_bot(GUILD, Session, crypto, LAUNCH_CONFIG)
    
    bot.run(TOKEN)
    