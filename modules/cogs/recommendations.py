from typing import Callable

from discord.ext import commands

class Recommendations(commands.Cog):

    _bot: commands.Bot
    _recommendation_callback: Callable

    def __init__(self, bot: commands.Bot, recommendation_callback: Callable) -> None:
        self._bot = bot
        self._recommendation_callback = recommendation_callback

    @commands.command(name="test2")
    async def test(self, ctx: commands.Context) -> None:
        """/test"""
        answer = self._recommendation_callback()
        await ctx.send(answer, ephemeral=True)
