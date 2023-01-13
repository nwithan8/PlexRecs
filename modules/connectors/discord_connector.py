import asyncio
from typing import Callable

import discord
from discord import app_commands
from discord.ext import commands

import modules.logs as logging
from modules.analytics import GoogleAnalytics
from modules.config_parser import DiscordConfig

from modules.cogs.recommendations import Recommendations

class DiscordConnector(commands.Cog):

    _analytics: GoogleAnalytics
    _token: str
    _bot: commands.Bot

    def __init__(self, config: DiscordConfig, analytics: GoogleAnalytics):
        self._analytics = analytics

        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True

        # Store Discord token
        self._token = config.bot_token

        # Initialize a Discord bot
        self._bot = commands.Bot(command_prefix=config.bot_prefix, intents=intents)

    async def load_recommendation_commands(self, recommendation_callback: Callable):
        # Load commands via cogs
        logging.info("Loading recommendation commands...")
        await self._bot.add_cog(Recommendations(bot=self._bot, recommendation_callback=recommendation_callback))
        for command in self._bot.commands:
            logging.info(f"Loaded command: {command.name}")

    async def connect(self):
        # Connect bot to Discord
        logging.info("Connecting to Discord...")
        await self._bot.start(token=self._token, reconnect=True) # Needs to be the last thing started



