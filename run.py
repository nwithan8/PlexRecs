import discord
from discord.ext import commands
import credentials

bot = commands.Bot(credentials.BOT_PREFIX)

formatter = commands.HelpCommand(show_check_failure=False)

exts = [
    "__init__.py"
]
for ext in exts:
    bot.load_extension(ext)


@bot.event
async def on_ready():
    print(f'\n\nLogged in as : {bot.user.name} - {bot.user.id}\nVersion: {discord.__version__}\n')
    await bot.change_presence(status=discord.Status.idle, activity=discord.Game(name=f'the waiting game | {PREFIX}'))
    print(f'Successfully logged in and booted...!\n')


print(
    "PlexRecs  Copyright (C) 2020  Nathan Harris\nThis program comes with ABSOLUTELY NO WARRANTY.\nThis is free "
    "software, and you are welcome to redistribute it\nunder certain conditions.")
bot.run(credentials.DISCORD_BOT_TOKEN)
