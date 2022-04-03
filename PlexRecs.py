import asyncio
import inspect
import sys
from typing import Union

import discord
from discord.ext import commands, tasks

import credentials
import modules.analytics as ga
import modules.imdb_connector as imdb
import modules.picker as picker
import modules.plex_connector as plex_connector
import modules.trakt_connector as trakt_connector
from modules import discord_utils
from modules.library_database import PlexContentDatabase, Content
from modules.logs import *

analytics = ga.GoogleAnalytics(analytics_id='UA-174268200-1', anonymous_ip=True,
                               do_not_track=not credentials.ALLOW_ANALYTICS)

plex = plex_connector.PlexConnector(url=credentials.PLEX_URL, token=credentials.PLEX_TOKEN,
                                    server_name=credentials.PLEX_SERVER_NAME,
                                    library_list=credentials.LIBRARIES, tautulli_url=credentials.TAUTULLI_BASE_URL,
                                    tautulli_key=credentials.TAUTULLI_API_KEY, analytics=analytics,
                                    database=PlexContentDatabase("content.db"))

trakt = trakt_connector.TraktConnector(username=credentials.TRAKT_USERNAME,
                                       client_id=credentials.TRAKT_CLIENT_ID,
                                       client_secret=credentials.TRAKT_CLIENT_SECRET, analytics=analytics)
trakt.store_public_lists(lists_dict=credentials.TRAKT_LISTS)

emoji_numbers = [u"1\u20e3", u"2\u20e3", u"3\u20e3", u"4\u20e3", u"5\u20e3"]


def error_and_analytics(error_message, function_name):
    error(error_message)
    analytics.event(event_category="Error", event_action=function_name, random_uuid_if_needed=True)


def find_rec(media_type: str, unwatched: bool = False, username: str = None, rating: float = None,
             above: bool = True, trakt_list_name: str = None, attempts: int = 10):
    """
    :param attempts:
    :param trakt_list_name:
    :param above:
    :param rating:
    :param username:
    :param unwatched:
    :param media_type: 'movie', 'show' or 'artist'
    :return:
    """
    try:
        if unwatched:
            return picker.pick_unwatched(plex_connector=plex, username=username, media_type=media_type,
                                         attempts=attempts)
        elif rating:
            return picker.pick_with_rating(plex_connector=plex, media_type=media_type, rating=rating, above=above,
                                           attempts=attempts)
        elif trakt_list_name:
            return picker.pick_from_trakt_list(trakt_connector=trakt, trakt_list_name=trakt_list_name,
                                               plex_connector=plex, attempts=attempts)
        else:
            return picker.pick_random(plex_connector=plex, media_type=media_type)
    except Exception as e:
        error_and_analytics(error_message=f"Error in findRec: {e}", function_name=inspect.currentframe().f_code.co_name)
    return False


def make_recommendation(media_type: str, unwatched: bool = False, plex_username: str = None, rating: float = None,
                        above: bool = True, trakt_list_name: str = None):
    if unwatched:
        if not plex_username:
            return "Please include a Plex username"
        recommendation = find_rec(media_type=media_type, unwatched=True, username=plex_username)
        if not recommendation:
            return "I couldn't find that Plex username", None, None
        if recommendation == "Too many attempts":
            return "Sorry, it took too long to find something for you", None, None
    elif rating:
        recommendation = find_rec(media_type=media_type, rating=rating, above=above)
        if recommendation == "Too many attempts":
            return "Sorry, it took too long to find something for you", None, None
    elif trakt_list_name:
        recommendation = find_rec(media_type=media_type, trakt_list_name=trakt_list_name)
        if recommendation == "Too many attempts":
            return "Sorry, it took too long to find something for you", None, None
    else:
        recommendation = find_rec(media_type=media_type, unwatched=False)
    embed = discord_utils.make_embed(plex=plex, media_item=recommendation, analytics=analytics)
    return f"How about {recommendation.Title}?", embed, recommendation


class PlexRecs(commands.Cog):

    async def user_response(self, ctx, media_type: str, media_item: Content):
        if str(ctx.message.author.id) == str(credentials.OWNER_DISCORD_ID):
            response, number_of_players = plex.get_available_players(media_type=media_type)
            if response:
                ask_about_player = True
                while ask_about_player:
                    def check(react, react_user, num_players):
                        return str(react.emoji) in emoji_numbers[:number_of_players] \
                               and react_user.id == credentials.OWNER_DISCORD_ID

                    player_question = await ctx.send(response)
                    try:
                        for i in range(0, number_of_players - 1):
                            await player_question.add_reaction(emoji_numbers[i])
                        reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
                        if reaction:
                            player_number = emoji_numbers.index(str(reaction.emoji))
                            media_item = plex.get_full_media_item(content_media_item=media_item)
                            if media_item:
                                plex.play_media(player_number, media_item)
                            else:
                                await ctx.send(
                                    f"Sorry, something went wrong while loading that {media_type}.")
                    except asyncio.TimeoutError:
                        await player_question.delete()
                        ask_about_player = False

    @tasks.loop(minutes=60.0)  # update library every hour
    async def make_libraries(self):
        plex.populate_libraries()

    @commands.group(aliases=['recommend', 'suggest', 'rec', 'sugg'], pass_context=True)
    async def plex_rec(self, ctx: commands.Context, media_type: str):
        """
        Get a recommendation item from Plex.
        Required:
        - what kind of content you want (i.e. 'movie', 'show', 'anime', 'song')

        Optional filters:
        - new [PLEX_USERNAME]: Only get recommended something you haven't played before
        - imdb +/-[SCORE]: Only get recommended something that scores better/worse than [SCORE] on IMDb
        - trakt [LIST_NAME]: Only get recommended something from a specific Trakt.tv list
        - genre [GENRE]: Only get recommended something of a specific genre
        - year [YEAR]: Only get recommended something from a specific year
        Other Plex filters are supported:
        - actor [ACTOR_ID]
        - collection [COLLECTION_ID]
        - contentRating [CONTENT_RATING]
        - country [COUNTRY]
        - decade [DECADE]
        - director [DIRECTOR_ID]
        - network [NETWORK_NAME]
        - resolution [RESOLUTION]
        - studio [STUDIO_NAME]
        """
        if ctx.invoked_subcommand is None:
            if media_type.lower() not in plex.library_config.keys():
                accepted_types = "', '".join(plex.library_config.keys())
                await ctx.send(f"Please try again, indicating '{accepted_types}'")
            else:
                hold_message = await ctx.send(
                    "Looking for a{} {}...".format("n" if (media_type[0] in ['a', 'e', 'i', 'o', 'u']) else "",
                                                   media_type))
                async with ctx.typing():
                    response, embed, media_item = make_recommendation(media_type, False, None)
                await hold_message.delete()
                if embed is not None:
                    await ctx.send(response, embed=embed)
                else:
                    await ctx.send(response)
                await self.user_response(ctx=ctx, media_type=media_type, media_item=media_item)
                analytics.event(event_category="Rec", event_action="Successful rec")

    @plex_rec.error
    async def plex_rec_error(self, ctx, error_msg):
        error_and_analytics(error_message=error_msg, function_name=inspect.currentframe().f_code.co_name)
        await ctx.send("Sorry, something went wrong while looking for a recommendation.")

    @plex_rec.command(name="new", aliases=['unwatched', 'unseen', 'unlistened'])
    async def plex_rec_new(self, ctx: commands.Context, plex_username: str):
        """
        Get a new movie, show or artist recommendation
        Include your Plex username
        """
        media_type = None
        for group in plex.library_config.keys():
            if group in ctx.message.content:
                media_type = group
                break
        if not media_type:
            accepted_types = "', '".join(plex.library_config.keys())
            await ctx.send(f"Please try again, indicating '{accepted_types}'")
        else:
            hold_message = await ctx.send(f"Looking for a new {media_type}...")
            async with ctx.typing():
                response, embed, media_item = make_recommendation(media_type, True, plex_username)
            await hold_message.delete()
            if embed is not None:
                await ctx.send(response, embed=embed)
            else:
                await ctx.send(response)
            analytics.event(event_category="Rec", event_action="Successful new rec")
            await self.user_response(ctx=ctx, media_type=media_type, media_item=media_item)

    @plex_rec_new.error
    async def plex_rec_new_error(self, ctx, error_msg):
        error_and_analytics(error_message=error_msg, function_name=inspect.currentframe().f_code.co_name)
        await ctx.send("Sorry, something went wrong while looking for a new recommendation.")

    @plex_rec.command(name="above", aliases=['over', 'better'])
    async def plex_rec_above(self, ctx: commands.Context, rating: Union[float, int]):
        """
        Get a movie or show above a certain IMDb rating (not music)
        Include your rating
        """
        media_type = None
        for group in plex.library_config.keys():
            if group in ctx.message.content:
                media_type = group
                break
        if not media_type or media_type not in ['movie', 'show']:
            await ctx.send(f"Sorry, this feature only works for movies and TV shows.")
        else:
            hold_message = await ctx.send(f"Looking for a {media_type} that's rated at least {rating} on IMDb...")
            async with ctx.typing():
                response, embed, media_item = make_recommendation(media_type=media_type, rating=float(rating),
                                                                  above=True)
            await hold_message.delete()
            if embed is not None:
                await ctx.send(response, embed=embed)
            else:
                await ctx.send(response)
            analytics.event(event_category="Rec", event_action="Successful IMDb above rec")
            await self.user_response(ctx=ctx, media_type=media_type, media_item=media_item)

    @plex_rec_above.error
    async def plex_rec_above_error(self, ctx, error_msg):
        error_and_analytics(error_message=error_msg, function_name=inspect.currentframe().f_code.co_name)
        await ctx.send("Sorry, something went wrong while looking for a new recommendation.")

    @plex_rec.command(name="below", aliases=['under', 'worse'])
    async def plex_rec_below(self, ctx: commands.Context, rating: Union[float, int]):
        """
        Get a movie or show below a certain IMDb rating (not music)
        Include your rating
        """
        media_type = None
        for group in plex.library_config.keys():
            if group in ctx.message.content:
                media_type = group
                break
        if not media_type or media_type not in ['movie', 'show']:
            await ctx.send(f"Sorry, this feature only works for movies and TV shows.")
        else:
            hold_message = await ctx.send(f"Looking for a {media_type} that's rated less than {rating} on IMDb...")
            async with ctx.typing():
                response, embed, media_item = make_recommendation(media_type=media_type, rating=float(rating),
                                                                  above=False)
            await hold_message.delete()
            if embed is not None:
                await ctx.send(response, embed=embed)
            else:
                await ctx.send(response)
            analytics.event(event_category="Rec", event_action="Successful IMDb below rec")
            await self.user_response(ctx=ctx, media_type=media_type, media_item=media_item)

    @plex_rec_below.error
    async def plex_rec_below_error(self, ctx, error_msg):
        error_and_analytics(error_message=error_msg, function_name=inspect.currentframe().f_code.co_name)
        await ctx.send("Sorry, something went wrong while looking for a new recommendation.")

    @plex_rec.command(name="trakt")
    async def plex_rec_trakt(self, ctx: commands.Context, *, list_name: str):
        """
        Get a movie or show from a specific Trakt.tv list

        Heads up: Large Trakt list may take a while to parse, and your request may time out.
        Once a choice is made from Trakt, the item is searched for in your Plex library. False matches are possible.
        """
        media_type = None
        for group in plex.library_config.keys():
            if group in ctx.message.content:
                media_type = group
                break
        if not media_type or media_type not in ['movie', 'show']:
            await ctx.send(f"Sorry, this feature only works for movies and TV shows.")
        else:
            hold_message = await ctx.send(f"Looking for a {media_type} from the '{list_name}' list on Trakt.tv")
            async with ctx.typing():
                response, embed, media_item = make_recommendation(media_type=media_type, trakt_list_name=list_name)
            await hold_message.delete()
            if embed is not None:
                await ctx.send(response, embed=embed)
            else:
                await ctx.send(response)
            analytics.event(event_category="Rec", event_action="Successful Trakt rec")
            await self.user_response(ctx=ctx, media_type=media_type, media_item=media_item)

    @plex_rec_trakt.error
    async def plex_rec_trakt_error(self, ctx, error_msg):
        error_and_analytics(error_message=error_msg, function_name=inspect.currentframe().f_code.co_name)
        await ctx.send("Sorry, something went wrong while looking for a new recommendation.")

    def __init__(self, bot):
        self.bot = bot
        analytics.event(event_category="Platform", event_action=sys.platform)
        info("Updating Plex libraries...")
        self.make_libraries.start()


def setup(bot):
    bot.add_cog(PlexRecs(bot))
