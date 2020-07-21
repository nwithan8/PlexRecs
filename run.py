import discord
from discord.ext import commands
import credentials
from modules.logs import *
import logging

logging.basicConfig(format='%(levelname)s:%(message)s',
                    level=(logging.ERROR if credentials.SUPPRESS_LOGS else logging.INFO))

bot = commands.Bot(credentials.BOT_PREFIX)

formatter = commands.HelpCommand(show_check_failure=False)

print(
    "PlexRecs  Copyright (C) 2020  Nathan Harris\nThis program comes with ABSOLUTELY NO WARRANTY.\nThis is free "
    "software, and you are welcome to redistribute it\nunder certain conditions.\n")
info("Starting application...")

exts = [
    "PlexRecs"
]
for ext in exts:
    bot.load_extension(ext)


@bot.event
async def on_ready():
    info(f'\n\nLogged in as : {bot.user.name} - {bot.user.id}\nVersion: {discord.__version__}\n')
    await bot.change_presence(status=discord.Status.idle, activity=discord.Game(name=f'in the REC league | {credentials.BOT_PREFIX}'))
    info(f'Successfully logged in and booted...!\n')


if __name__ == '__main__':
    info("Connecting to Discord...")
    bot.run(credentials.DISCORD_BOT_TOKEN)
