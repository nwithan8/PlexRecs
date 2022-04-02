import asyncio
import discord
from discord.ext import commands, tasks
import credentials
import sys
from typing import Union

from modules.logs import *
import modules.plex_connector as plex_connector
import modules.trakt_connector as trakt_connector
import modules.imdb_connector as imdb
import modules.picker as picker
import modules.analytics as ga

analytics = ga.GoogleAnalytics(analytics_id='UA-174268200-1', anonymous_ip=True,
                               do_not_track=not credentials.ALLOW_ANALYTICS)

plex = plex_connector.PlexConnector(url=credentials.PLEX_URL, token=credentials.PLEX_TOKEN,
                                    server_name=credentials.PLEX_SERVER_NAME,
                                    library_list=credentials.LIBRARIES, tautulli_url=credentials.TAUTULLI_BASE_URL,
                                    tautulli_key=credentials.TAUTULLI_API_KEY, analytics=analytics)

trakt = trakt_connector.TraktConnector(username=credentials.TRAKT_USERNAME,
                                       client_id=credentials.TRAKT_CLIENT_ID,
                                       client_secret=credentials.TRAKT_CLIENT_SECRET, analytics=analytics)
trakt.store_public_lists(lists_dict=credentials.TRAKT_LISTS)

emoji_numbers = [u"1\u20e3", u"2\u20e3", u"3\u20e3", u"4\u20e3", u"5\u20e3"]


def error_and_analytics(error_message, function_name):
    error(error_message)
    analytics.event(event_category="Error", event_action=function_name, random_uuid_if_needed=True)


def make_embed(media_item):
    imdb_item = imdb.get_imdb_item(media_item.title, analytics=analytics)
    embed = None
    if credentials.RETURN_PLEX_URL:
        url = f"https://app.plex.tv/desktop#!/server/{plex.server_id}/details?key=%2Flibrary%2Fmetadata%2F{media_item.ratingKey}"
        embed = discord.Embed(title=media_item.title,
                              url=url,
                              description=f"Watch it on {credentials.PLEX_SERVER_NAME}")
        embed.add_field(name="\u200b", value=f"[Click here to watch on Plex]({url})")
    else:
        url = f"https://www.imdb.com/title/{imdb_item.imdb_id}"
        embed = discord.Embed(title=media_item.title,
                              url=url,
                              description=f"View on IMDb")
        embed.add_field(name="\u200b", value=f"[Click here to view on IMDb]({url})")
    embed.add_field(name="Summary", value=imdb_item.plot_outline, inline=False)
    embed.add_field(name="Release Date", value=imdb_item.release_date, inline=False)
    if media_item.type not in ['artist', 'album', 'track']:
        try:
            embed.set_image(url=str(imdb_item.image.url))
        except:
            pass
    return embed


def find_rec(media_type: str = None, unwatched: bool = False, username: str = None, rating: float = None,
             above: bool = True, trakt_list_name: str = None, attempts: int = 0):
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
            return picker.pick_unwatched(
                history=plex.get_user_history(username=username, section_ids=plex.libraries[media_type][0]),
                media_list=plex.libraries[media_type][1])
        elif rating:
            return picker.pick_with_rating(a_list=plex.libraries[media_type][1], rating=rating, above=above)
        elif trakt_list_name:
            trakt_list = trakt.get_list_items(list_name=trakt_list_name)
            return picker.pick_from_trakt_list(trakt_list=trakt_list, plex_instance=plex)
        else:
            return picker.pick_random(a_list=plex.libraries[media_type][1])
    except Exception as e:
        error_and_analytics(error_message=f"Error in findRec: {e}", function_name='findRec')
    return False


def makeRecommendation(media_type, unwatched: bool = False, PlexUsername: str = None, rating: float = None,
                       above: bool = True, trakt_list_name: str = None):
    if unwatched:
        if not PlexUsername:
            return "Please include a Plex username"
        recommendation = find_rec(media_type=media_type, unwatched=True, username=PlexUsername)
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
    embed = make_embed(recommendation)
    return f"How about {recommendation.title}?", embed, recommendation


class PlexRecs(commands.Cog):

    async def user_response(self, ctx, media_type, media_item):
        if str(ctx.message.author.id) == str(credentials.OWNER_DISCORD_ID):
            response, number_of_players = plex.get_available_players(media_type=media_type)
            if response:
                ask_about_player = True
                while ask_about_player:
                    try:
                        def check(react, react_user, num_players):
                            return str(react.emoji) in emoji_numbers[
                                                       :number_of_players] and react_user.id == credentials.OWNER_DISCORD_ID

                        player_question = await ctx.send(response)
                        for i in range(0, number_of_players - 1):
                            await player_question.add_reaction(emoji_numbers[i])
                        reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
                        if reaction:
                            player_number = emoji_numbers.index(str(reaction.emoji))
                            media_item = plex.get_full_media_item(media_item)
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
        plex.make_libraries()

    @commands.group(aliases=['recommend', 'suggest', 'rec', 'sugg'], pass_context=True)
    async def plex_rec(self, ctx: commands.Context, media_type: str):
        """
        Movie, show or artist recommendation from Plex

        Say 'movie', 'show' or 'artist'
        Use 'rec <media_type> new <PlexUsername>' for an unwatched recommendation.
        Use 'rec <media_type> above/below <rating>' for a movie above/below a certain IMDb score.
        """
        if ctx.invoked_subcommand is None:
            if media_type.lower() not in plex.libraries.keys():
                accepted_types = "', '".join(plex.libraries.keys())
                await ctx.send(f"Please try again, indicating '{accepted_types}'")
            else:
                hold_message = await ctx.send(
                    "Looking for a{} {}...".format("n" if (media_type[0] in ['a', 'e', 'i', 'o', 'u']) else "",
                                                   media_type))
                async with ctx.typing():
                    response, embed, media_item = makeRecommendation(media_type, False, None)
                await hold_message.delete()
                if embed is not None:
                    await ctx.send(response, embed=embed)
                else:
                    await ctx.send(response)
                await self.user_response(ctx=ctx, media_type=media_type, media_item=media_item)
                analytics.event(event_category="Rec", event_action="Successful rec")

    @plex_rec.error
    async def plex_rec_error(self, ctx, error_msg):
        error_and_analytics(error_message=error_msg, function_name='plex_rec')
        await ctx.send("Sorry, something went wrong while looking for a recommendation.")

    @plex_rec.command(name="new", aliases=['unwatched', 'unseen', 'unlistened'])
    async def plex_rec_new(self, ctx: commands.Context, plex_username: str):
        """
        Get a new movie, show or artist recommendation
        Include your Plex username
        """
        media_type = None
        for group in plex.libraries.keys():
            if group in ctx.message.content:
                media_type = group
                break
        if not media_type:
            accepted_types = "', '".join(plex.libraries.keys())
            await ctx.send(f"Please try again, indicating '{accepted_types}'")
        else:
            hold_message = await ctx.send(f"Looking for a new {media_type}...")
            async with ctx.typing():
                response, embed, media_item = makeRecommendation(media_type, True, plex_username)
            await hold_message.delete()
            if embed is not None:
                await ctx.send(response, embed=embed)
            else:
                await ctx.send(response)
            analytics.event(event_category="Rec", event_action="Successful new rec")
            await self.user_response(ctx=ctx, media_type=media_type, media_item=media_item)

    @plex_rec_new.error
    async def plex_rec_new_error(self, ctx, error_msg):
        error_and_analytics(error_message=error_msg, function_name='plex_rec_new')
        await ctx.send("Sorry, something went wrong while looking for a new recommendation.")

    @plex_rec.command(name="above", aliases=['over', 'better'])
    async def plex_rec_above(self, ctx: commands.Context, rating: Union[float, int]):
        """
        Get a movie or show above a certain IMDb rating (not music)
        Include your rating
        """
        media_type = None
        for group in plex.libraries.keys():
            if group in ctx.message.content:
                media_type = group
                break
        if not media_type or media_type not in ['movie', 'show']:
            await ctx.send(f"Sorry, this feature only works for movies and TV shows.")
        else:
            hold_message = await ctx.send(f"Looking for a {media_type} that's rated at least {rating} on IMDb...")
            async with ctx.typing():
                response, embed, media_item = makeRecommendation(media_type=media_type, rating=float(rating), above=True)
            await hold_message.delete()
            if embed is not None:
                await ctx.send(response, embed=embed)
            else:
                await ctx.send(response)
            analytics.event(event_category="Rec", event_action="Successful IMDb above rec")
            await self.user_response(ctx=ctx, media_type=media_type, media_item=media_item)

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
        media_type = None
        for group in plex.libraries.keys():
            if group in ctx.message.content:
                media_type = group
                break
        if not media_type or media_type not in ['movie', 'show']:
            await ctx.send(f"Sorry, this feature only works for movies and TV shows.")
        else:
            hold_message = await ctx.send(f"Looking for a {media_type} that's rated less than {rating} on IMDb...")
            async with ctx.typing():
                response, embed, media_item = makeRecommendation(media_type=media_type, rating=float(rating), above=False)
            await hold_message.delete()
            if embed is not None:
                await ctx.send(response, embed=embed)
            else:
                await ctx.send(response)
            analytics.event(event_category="Rec", event_action="Successful IMDb below rec")
            await self.user_response(ctx=ctx, media_type=media_type, media_item=media_item)

    @plex_rec_below.error
    async def plex_rec_below_error(self, ctx, error_msg):
        error_and_analytics(error_message=error_msg, function_name='plex_rec_below')
        await ctx.send("Sorry, something went wrong while looking for a new recommendation.")

    @plex_rec.command(name="trakt")
    async def plex_rec_trakt(self, ctx: commands.Context, *, list_name: str):
        """
        Get a movie or show from a specific Trakt.tv list

        Heads up: Large Trakt list may take a while to parse, and your request may time out.
        Once a choice is made from Trakt, the item is searched for in your Plex library. False matches are possible.
        """
        media_type = None
        for group in plex.libraries.keys():
            if group in ctx.message.content:
                media_type = group
                break
        if not media_type or media_type not in ['movie', 'show']:
            await ctx.send(f"Sorry, this feature only works for movies and TV shows.")
        else:
            hold_message = await ctx.send(f"Looking for a {media_type} from the '{list_name}' list on Trakt.tv")
            async with ctx.typing():
                response, embed, media_item = makeRecommendation(media_type=media_type, trakt_list_name=list_name)
            await hold_message.delete()
            if embed is not None:
                await ctx.send(response, embed=embed)
            else:
                await ctx.send(response)
            analytics.event(event_category="Rec", event_action="Successful Trakt rec")
            await self.user_response(ctx=ctx, media_type=media_type, media_item=media_item)

    @plex_rec_trakt.error
    async def plex_rec_trakt_error(self, ctx, error_msg):
        error_and_analytics(error_message=error_msg, function_name='plex_rec_trakt')
        await ctx.send("Sorry, something went wrong while looking for a new recommendation.")

    def __init__(self, bot):
        self.bot = bot
        analytics.event(event_category="Platform", event_action=sys.platform)
        info("Updating Plex libraries...")
        self.make_libraries.start()


def setup(bot):
    bot.add_cog(PlexRecs(bot))
