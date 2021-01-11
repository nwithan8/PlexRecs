import asyncio
import discord
from discord.ext import commands, tasks
import credentials
import sys
from typing import Union, List


import info
from modules.logs import *
import modules.plex_connector as plex_connector
import modules.trakt_connector as trakt_connector
import modules.picker as picker
import modules.analytics as ga
import modules.discord_utils as discord_utils

analytics = ga.GoogleAnalytics(analytics_id='UA-174268200-1',
                               anonymous_ip=True,
                               do_not_track=not credentials.ALLOW_ANALYTICS)

plex = plex_connector.PlexConnector(url=credentials.PLEX_URL,
                                    token=credentials.PLEX_TOKEN,
                                    server_name=credentials.PLEX_SERVER_NAME,
                                    library_list=credentials.LIBRARIES,
                                    tautulli_url=credentials.TAUTULLI_BASE_URL,
                                    tautulli_key=credentials.TAUTULLI_API_KEY,
                                    analytics=analytics)

trakt = trakt_connector.TraktConnector(username=credentials.TRAKT_USERNAME,
                                       client_id=credentials.TRAKT_CLIENT_ID,
                                       client_secret=credentials.TRAKT_CLIENT_SECRET,
                                       analytics=analytics)
trakt.store_public_lists(lists_dict=credentials.TRAKT_LISTS)

emoji_numbers = [u"1\u20e3", u"2\u20e3", u"3\u20e3", u"4\u20e3", u"5\u20e3"]

def apply_filters(media_type: str, filters: List[str]):
    for pair in iter(filters):
        key = pair
        value = next(pair)



def error_and_analytics(error_message, function_name):
    error(error_message)
    analytics.event(event_category="Error",
                    event_action=function_name,
                    random_uuid_if_needed=True)


def findRec(mediaType: str = None, unwatched: bool = False, username: str = None, rating: float = None,
            above: bool = True, trakt_list_name: str = None, attempts: int = 0):
    """

    :param attempts:
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
                history=plex.get_user_history(username=username,
                                              sections_ids=plex.libraries[mediaType][0]),
                mediaList=plex.libraries[mediaType][1])
        elif rating:
            return picker.pick_with_rating(aList=plex.libraries[mediaType][1],
                                           rating=rating,
                                           above=above)
        elif trakt_list_name:
            trakt_list = trakt.get_list_items(list_name=trakt_list_name)
            return picker.pick_from_trakt_list(trakt_list=trakt_list,
                                               plex_instance=plex)
        else:
            return picker.pick_random(aList=plex.libraries[mediaType][1])
    except Exception as e:
        error_and_analytics(error_message=f"Error in findRec: {e}",
                            function_name='findRec')
    return False


def make_recommendation(media_type, unwatched: bool = False, plex_username: str = None, rating: float = None,
                       above: bool = True, trakt_list_name: str = None):
    if unwatched:
        if not plex_username:
            return "Please include a Plex username"
        recommendation = findRec(mediaType=media_type,
                                 unwatched=True,
                                 username=plex_username)
        if not recommendation:
            return "I couldn't find that Plex username", None, None
        if recommendation == "Too many attempts":
            return "Sorry, it took too long to find something for you", None, None
    elif rating:
        recommendation = findRec(mediaType=media_type,
                                 rating=rating,
                                 above=above)
        if recommendation == "Too many attempts":
            return "Sorry, it took too long to find something for you", None, None
    elif trakt_list_name:
        recommendation = findRec(mediaType=media_type,
                                 trakt_list_name=trakt_list_name)
        if recommendation == "Too many attempts":
            return "Sorry, it took too long to find something for you", None, None
    else
        recommendation = findRec(mediaType=media_type,
                                 unwatched=False)
    embed = discord_utils.make_embed(plex=plex, analytics=analytics, media_item=recommendation)
    return f"How about {recommendation.title}?", embed, recommendation


class PlexRecs(commands.Cog):

    async def userResponse(self, ctx, mediaType, mediaItem):
        if str(ctx.message.author.id) == str(credentials.OWNER_DISCORD_ID):
            response, num_of_players = plex.get_available_players(mediaType=mediaType)
            if response:
                askAboutPlayer = True
                while askAboutPlayer:
                    try:
                        def check(react, react_user, num_players):
                            return str(react.emoji) in emoji_numbers[:num_of_players] \
                                   and react_user.id == credentials.OWNER_DISCORD_ID

                        playerQuestion = await ctx.send(response)
                        for i in range(0, num_of_players - 1):
                            await playerQuestion.add_reaction(emoji_numbers[i])
                        reaction, user = await self.bot.wait_for('reaction_add',
                                                                 timeout=60.0,
                                                                 check=check)
                        if reaction:
                            playerNumber = emoji_numbers.index(str(reaction.emoji))
                            mediaItem = plex.get_full_media_item(mediaItem)
                            if mediaItem:
                                plex.play_media(playerNumber, mediaItem)
                            else:
                                await ctx.send(
                                    f"Sorry, something went wrong while loading that {mediaType}.")
                    except asyncio.TimeoutError:
                        await playerQuestion.delete()
                        askAboutPlayer = False

    @tasks.loop(minutes=60.0)  # update library every hour
    async def makeLibraries(self):
        plex.make_libraries()

    @commands.group(aliases=['recommend', 'suggest', 'rec', 'sugg'],
                    pass_context=True)
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
                    response, embed, mediaItem = make_recommendation(media_type=mediaType, False, None)
                await holdMessage.delete()
                if embed is not None:
                    await ctx.send(response, embed=embed)
                else:
                    await ctx.send(response)
                await self.userResponse(ctx=ctx,
                                        mediaType=mediaType,
                                        mediaItem=mediaItem)
                analytics.event(event_category="Rec",
                                event_action="Successful rec")

    @plex_rec.error
    async def plex_rec_error(self, ctx, error_msg):
        error_and_analytics(error_message=error_msg,
                            function_name='plex_rec')
        await ctx.send("Sorry, something went wrong while looking for a recommendation.")

    @plex_rec.command(name="filter",
                      aliases=['params'])
    async def plex_rec_filter(self, ctx: commands.Context, *, filters: str):



    @plex_rec_filter.error
    async def plex_rec_filter_error(self, ctx, error_msg):
        error_and_analytics(error_message=error_msg,
                            function_name='plex_rec_filter')
        await ctx.send("Sorry, something went wrong while applying your filters.")

    @plex_rec.command(name="new",
                      aliases=['unwatched', 'unseen', 'unlistened'])
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
            analytics.event(event_category="Rec",
                            event_action="Successful new rec")
            await self.userResponse(ctx=ctx,
                                    mediaType=mediaType,
                                    mediaItem=mediaItem)

    @plex_rec_new.error
    async def plex_rec_new_error(self, ctx, error_msg):
        error_and_analytics(error_message=error_msg,
                            function_name='plex_rec_new')
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
                response, embed, mediaItem = make_recommendation(media_type=mediaType,
                                                                 rating=float(rating),
                                                                 above=True)
            await holdMessage.delete()
            if embed is not None:
                await ctx.send(response,
                               embed=embed)
            else:
                await ctx.send(response)
            analytics.event(event_category="Rec",
                            event_action="Successful IMDb above rec")
            await self.userResponse(ctx=ctx,
                                    mediaType=mediaType,
                                    mediaItem=mediaItem)

    @plex_rec_above.error
    async def plex_rec_above_error(self, ctx, error_msg):
        error_and_analytics(error_message=error_msg, function_name='plex_rec_above')
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
                response, embed, mediaItem = make_recommendation(media_type=mediaType,
                                                                rating=float(rating),
                                                                above=False)
            await holdMessage.delete()
            if embed is not None:
                await ctx.send(response,
                               embed=embed)
            else:
                await ctx.send(response)
            analytics.event(event_category="Rec",
                            event_action="Successful IMDb below rec")
            await self.userResponse(ctx=ctx,
                                    mediaType=mediaType,
                                    mediaItem=mediaItem)

    @plex_rec_below.error
    async def plex_rec_below_error(self, ctx, error_msg):
        error_and_analytics(error_message=error_msg,
                            function_name='plex_rec_below')
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
                response, embed, mediaItem = make_recommendation(media_type=mediaType,
                                                                trakt_list_name=list_name)
            await holdMessage.delete()
            if embed is not None:
                await ctx.send(response,
                               embed=embed)
            else:
                await ctx.send(response)
            analytics.event(event_category="Rec",
                            event_action="Successful Trakt rec")
            await self.userResponse(ctx=ctx,
                                    mediaType=mediaType,
                                    mediaItem=mediaItem)

    @plex_rec_trakt.error
    async def plex_rec_trakt_error(self, ctx, error_msg):
        error_and_analytics(error_message=error_msg,
                            function_name='plex_rec_trakt')
        await ctx.send("Sorry, something went wrong while looking for a new recommendation.")

    def __init__(self, bot):
        self.bot = bot
        analytics.event(event_category="Platform",
                        event_action=sys.platform)
        info("Updating Plex libraries...")
        self.makeLibraries.start()


def setup(bot):
    print(info.COPYRIGHT_MESSAGE)
    bot.add_cog(PlexRecs(bot))
