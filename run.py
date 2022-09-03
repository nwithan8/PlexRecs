import discord
from discord.ext import commands

from modules import config_parser
from modules.logs import *

config = config_parser.Config(app_name="PlexRecs", config_path="config.yaml")

logging.basicConfig(format='%(levelname)s:%(message)s',
                    level=logging.getLevelName(config.log_level))

bot = commands.Bot(command_prefix=config.discord.command_prefix, intents=discord.Intents.default())

formatter = commands.HelpCommand(show_check_failure=False)

info("Starting application...")

exts = [
    "PlexRecs"
]
for ext in exts:
    bot.load_extension(ext)


@bot.event
async def on_ready():
    info(f'\n\nLogged in as : {bot.user.name} - {bot.user.id}\nVersion: {discord.__version__}\n')
    await bot.change_presence(status=discord.Status.idle,
                              activity=discord.Game(name=f'in the REC league | {config.discord.bot_prefix}'))
    info(f'Successfully logged in and booted...!\n')


if __name__ == '__main__':
    info("Connecting to Discord...")
    bot.run(config.discord.bot_token)
