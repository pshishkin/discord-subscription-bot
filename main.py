import os
import logging
import discord
from dotenv import load_dotenv
from launch_config import LAUNCH_CONFIG_OPTIONS

from subscription_bot import create_bot
from dbmananaging import connect_to_db

if __name__ == '__main__':
    load_dotenv()
    TOKEN = os.getenv('DISCORD_TOKEN')
    GUILD = os.getenv('DISCORD_GUILD')
    DB_CONN_STRING = os.getenv('DB_CONN_STRING')
    LAUNCH_CONFIG = LAUNCH_CONFIG_OPTIONS[os.getenv('LAUNCH_MODE')]
    LOGGING_LEVEL = LAUNCH_CONFIG['logging_level']

    logging.basicConfig(level=logging.INFO)
    Session = connect_to_db(DB_CONN_STRING, LOGGING_LEVEL)

    bot = create_bot(GUILD, Session)
    bot.run(TOKEN)