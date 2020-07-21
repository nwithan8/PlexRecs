import asyncio
import discord
from discord.ext import commands, tasks
import credentials
from typing import Union

from modules.logs import *
import modules.plex_connector as plex_connector
import modules.trakt_connector as trakt_connector
import modules.imdb_connector as imdb
import modules.picker as picker

plex = plex_connector.PlexConnector(url=credentials.PLEX_URL, token=credentials.PLEX_TOKEN,
                                    server_id=credentials.PLEX_SERVER_ID, server_name=credentials.PLEX_SERVER_NAME,
                                    library_list=credentials.LIBRARIES, tautulli_url=credentials.TAUTULLI_BASE_URL,
                                    tautulli_key=credentials.TAUTULLI_API_KEY)

trakt = trakt_connector.TraktConnector(username=credentials.TRAKT_USERNAME,
                                       client_id=credentials.TRAKT_CLIENT_ID,
                                       client_secret=credentials.TRAKT_CLIENT_SECRET)
trakt.store_public_lists(lists_dict=credentials.TRAKT_LISTS)

emoji_numbers = [u"1\u20e3", u"2\u20e3", u"3\u20e3", u"4\u20e3", u"5\u20e3"]


def makeEmbed(mediaItem):
    imdb_item = imdb.get_imdb_item(mediaItem.title)
    embed = None
    if credentials.RETURN_PLEX_URL:
        embed = discord.Embed(title=mediaItem.title,
                              url=f"{credentials.PLEX_URL}/web/index.html#!/server/{credentials.PLEX_SERVER_ID}/details?key=%2Flibrary%2Fmetadata%2F{mediaItem.ratingKey}",
                              description=f"Watch it on {credentials.PLEX_SERVER_NAME}")
    else:
        embed = discord.Embed(title=mediaItem.title,
                              url=f"https://www.imdb.com/title/{imdb_item.imdb_id}",
                              description=f"View on IMDb")
    embed.add_field(name="Summary", value=imdb_item.plot_outline, inline=False)
    embed.add_field(name="Release Date", value=imdb_item.release_date, inline=False)
    if mediaItem.type not in ['artist', 'album', 'track']:
        try:
            embed.set_image(url=str(imdb_item.image.url))
        except:
            pass
    return embed


def findRec(mediaType: str = None, unwatched: bool = False, username: str = None, rating: float = None,
            above: bool = True, trakt_list_name: str = None, attempts: int = 0):
    """

    :param trakt_list_name:
    :param above:
    :param rating:
    :param username:
    :param unwatched:
    :param mediaType: 'movie', 'show' or 'artist'
    :return:
    """
    try:
        if unwatched:
            return picker.pick_unwatched(
                history=plex.get_user_history(username=username, sectionIDs=plex.libraries[mediaType][0]),
                mediaList=plex.libraries[mediaType][1])
        elif rating:
            return picker.pick_with_rating(aList=plex.libraries[mediaType][1], rating=rating, above=above)
        elif trakt_list_name:
            trakt_list = trakt.get_list_items(list_name=trakt_list_name)
            return picker.pick_from_trakt_list(trakt_list=trakt_list, plex_instance=plex)
        else:
            return picker.pick_random(aList=plex.libraries[mediaType][1])
    except Exception as e:
        error(f"Error in findRec: {e}")
    return False


def makeRecommendation(mediaType, unwatched: bool = False, PlexUsername: str = None, rating: float = None,
                       above: bool = True, trakt_list_name: str = None):
    if unwatched:
        if not PlexUsername:
            return "Please include a Plex username"
        recommendation = findRec(mediaType=mediaType, unwatched=True, username=PlexUsername)
        if not recommendation:
            return "I couldn't find that Plex username", None, None
        if recommendation == "Too many attempts":
            return "Sorry, it took too long to find something for you", None, None
    elif rating:
        recommendation = findRec(mediaType=mediaType, rating=rating, above=above)
        if recommendation == "Too many attempts":
            return "Sorry, it took too long to find something for you", None, None
    elif trakt_list_name:
        recommendation = findRec(mediaType=mediaType, trakt_list_name=trakt_list_name)
        if recommendation == "Too many attempts":
            return "Sorry, it took too long to find something for you", None, None
    else:
        recommendation = findRec(mediaType=mediaType, unwatched=False)
    embed = makeEmbed(recommendation)
    return f"How about {recommendation.title}?", embed, recommendation


class PlexRecs(commands.Cog):

    async def userResponse(self, ctx, mediaType, mediaItem):
        if str(ctx.message.author.id) == str(credentials.OWNER_DISCORD_ID):
            response, numberOfPlayers = plex.get_available_players(mediaType=mediaType)
            if response:
                askAboutPlayer = True
                while askAboutPlayer:
                    try:
                        def check(react, reactUser, numPlayers):
                            return str(react.emoji) in emoji_numbers[
                                                       :numberOfPlayers] and reactUser.id == credentials.OWNER_DISCORD_ID

                        playerQuestion = await ctx.send(response)
                        for i in range(0, numberOfPlayers - 1):
                            await playerQuestion.add_reaction(emoji_numbers[i])
                        reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
                        if reaction:
                            playerNumber = emoji_numbers.index(str(reaction.emoji))
                            mediaItem = plex.getFullMediaItem(mediaItem)
                            if mediaItem:
                                plex.playMedia(playerNumber, mediaItem)
                            else:
                                await ctx.send(
                                    f"Sorry, something went wrong while loading that {mediaType}.")
                    except asyncio.TimeoutError:
                        await playerQuestion.delete()
                        askAboutPlayer = False

    @tasks.loop(minutes=60.0)  # update library every hour
    async def makeLibraries(self):
        plex.make_libraries()

    @commands.group(aliases=['recommend', 'suggest', 'rec', 'sugg'], pass_context=True)
    async def plex_rec(self, ctx: commands.Context, mediaType: str):
        """
        Movie, show or artist recommendation from Plex

        Say 'movie', 'show' or 'artist'
        Use 'rec <mediaType> new <PlexUsername>' for an unwatched recommendation.
        Use 'rec <mediaType> above/below <rating>' for a movie above/below a certain IMDb score.
        """
        if ctx.invoked_subcommand is None:
            if mediaType.lower() not in plex.libraries.keys():
                acceptedTypes = "', '".join(plex.libraries.keys())
                await ctx.send(f"Please try again, indicating '{acceptedTypes}'")
            else:
                holdMessage = await ctx.send(
                    "Looking for a{} {}...".format("n" if (mediaType[0] in ['a', 'e', 'i', 'o', 'u']) else "",
                                                   mediaType))
                async with ctx.typing():
                    response, embed, mediaItem = makeRecommendation(mediaType, False, None)
                await holdMessage.delete()
                if embed is not None:
                    await ctx.send(response, embed=embed)
                else:
                    await ctx.send(response)
                await self.userResponse(ctx=ctx, mediaType=mediaType, mediaItem=mediaItem)

    @plex_rec.error
    async def plex_rec_error(self, ctx, error_msg):
        error(error_msg)
        await ctx.send("Sorry, something went wrong while looking for a recommendation.")

    @plex_rec.command(name="new", aliases=['unwatched', 'unseen', 'unlistened'])
    async def plex_rec_new(self, ctx: commands.Context, PlexUsername: str):
        """
        Get a new movie, show or artist recommendation
        Include your Plex username
        """
        mediaType = None
        for group in plex.libraries.keys():
            if group in ctx.message.content:
                mediaType = group
                break
        if not mediaType:
            acceptedTypes = "', '".join(plex.libraries.keys())
            await ctx.send(f"Please try again, indicating '{acceptedTypes}'")
        else:
            holdMessage = await ctx.send(f"Looking for a new {mediaType}...")
            async with ctx.typing():
                response, embed, mediaItem = makeRecommendation(mediaType, True, PlexUsername)
            await holdMessage.delete()
            if embed is not None:
                await ctx.send(response, embed=embed)
            else:
                await ctx.send(response)
            await self.userResponse(ctx=ctx, mediaType=mediaType, mediaItem=mediaItem)

    @plex_rec_new.error
    async def plex_rec_new_error(self, ctx, error_msg):
        error(error_msg)
        await ctx.send("Sorry, something went wrong while looking for a new recommendation.")

    @plex_rec.command(name="above", aliases=['over', 'better'])
    async def plex_rec_above(self, ctx: commands.Context, rating: Union[float, int]):
        """
        Get a movie or show above a certain IMDb rating (not music)
        Include your rating
        """
        mediaType = None
        for group in plex.libraries.keys():
            if group in ctx.message.content:
                mediaType = group
                break
        if not mediaType or mediaType not in ['movie', 'show']:
            await ctx.send(f"Sorry, this feature only works for movies and TV shows.")
        else:
            holdMessage = await ctx.send(f"Looking for a {mediaType} that's rated at least {rating} on IMDb...")
            async with ctx.typing():
                response, embed, mediaItem = makeRecommendation(mediaType=mediaType, rating=float(rating), above=True)
            await holdMessage.delete()
            if embed is not None:
                await ctx.send(response, embed=embed)
            else:
                await ctx.send(response)
            await self.userResponse(ctx=ctx, mediaType=mediaType, mediaItem=mediaItem)

    @plex_rec_above.error
    async def plex_rec_above_error(self, ctx, error_msg):
        error(error_msg)
        await ctx.send("Sorry, something went wrong while looking for a new recommendation.")

    @plex_rec.command(name="below", aliases=['under', 'worse'])
    async def plex_rec_below(self, ctx: commands.Context, rating: Union[float, int]):
        """
        Get a movie or show below a certain IMDb rating (not music)
        Include your rating
        """
        mediaType = None
        for group in plex.libraries.keys():
            if group in ctx.message.content:
                mediaType = group
                break
        if not mediaType or mediaType not in ['movie', 'show']:
            await ctx.send(f"Sorry, this feature only works for movies and TV shows.")
        else:
            holdMessage = await ctx.send(f"Looking for a {mediaType} that's rated less than {rating} on IMDb...")
            async with ctx.typing():
                response, embed, mediaItem = makeRecommendation(mediaType=mediaType, rating=float(rating), above=False)
            await holdMessage.delete()
            if embed is not None:
                await ctx.send(response, embed=embed)
            else:
                await ctx.send(response)
            await self.userResponse(ctx=ctx, mediaType=mediaType, mediaItem=mediaItem)

    @plex_rec_below.error
    async def plex_rec_below_error(self, ctx, error_msg):
        error(error_msg)
        await ctx.send("Sorry, something went wrong while looking for a new recommendation.")

    @plex_rec.command(name="trakt")
    async def plex_rec_trakt(self, ctx: commands.Context, *, list_name: str):
        """
        Get a movie or show from a specific Trakt.tv list

        Heads up: Large Trakt list may take a while to parse, and your request may time out.
        Once a choice is made from Trakt, the item is searched for in your Plex library. False matches are possible.
        """
        mediaType = None
        for group in plex.libraries.keys():
            if group in ctx.message.content:
                mediaType = group
                break
        if not mediaType or mediaType not in ['movie', 'show']:
            await ctx.send(f"Sorry, this feature only works for movies and TV shows.")
        else:
            holdMessage = await ctx.send(f"Looking for a {mediaType} from the '{list_name}' list on Trakt.tv")
            async with ctx.typing():
                response, embed, mediaItem = makeRecommendation(mediaType=mediaType, trakt_list_name=list_name)
            await holdMessage.delete()
            if embed is not None:
                await ctx.send(response, embed=embed)
            else:
                await ctx.send(response)
            await self.userResponse(ctx=ctx, mediaType=mediaType, mediaItem=mediaItem)

    @plex_rec_trakt.error
    async def plex_rec_trakt_error(self, ctx, error_msg):
        error(error_msg)
        await ctx.send("Sorry, something went wrong while looking for a new recommendation.")

    def __init__(self, bot):
        self.bot = bot
        info("Updating Plex libraries...")
        self.makeLibraries.start()


def setup(bot):
    bot.add_cog(PlexRecs(bot))
