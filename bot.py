# bot.py
import os

import discord
from dotenv import load_dotenv

from bot_logic import BotDiscordClient

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')

client = BotDiscordClient()

client.run(TOKEN)