import asyncio
import enum
import inspect
import sys
from pathlib import Path
from typing import Union, List, Callable

import discord
from discord import app_commands

from modules import config_parser, picker, discord_utils, statics
from modules.analytics import GoogleAnalytics
from modules.library_database import Content
from modules.logs import *
from modules.connectors.recommendation_connectors import RecommendationConnectors
from modules.utils import add_a_or_an


async def run_plex_library_update_service(refresh_time: int):
    while True:
        info("Updating Plex libraries...")
        # await self.plex.populate_libraries()
        await asyncio.sleep(refresh_time * 60)  # minutes to seconds


emoji_numbers = [
    "1️⃣",
    "2️⃣",
    "3️⃣",
    "4️⃣",
    "5️⃣",
]

config = config_parser.Config(app_name=statics.APP_NAME,
                              config_path=f"{Path(Path(__file__).parent / statics.CONFIG_FILE_NAME)}")

analytics = GoogleAnalytics(analytics_id=statics.GOOGLE_ANALYTICS_ID,
                            anonymous_ip=True,
                            do_not_track=not config.extras.allow_analytics)

logging.basicConfig(format='%(levelname)s:%(message)s', level=level_name_to_level(level_name=config.log_level))

intents = discord.Intents.default()
intents.members = True

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

recommendation_connectors = RecommendationConnectors(
    config=config,
    analytics=analytics
)

info("Starting application...")

analytics.event(event_category="Platform",
                event_action=sys.platform)

info("Loading Plex library service...")
# minimum 5-minute sleep time hard-coded, trust me, don't DDoS your server
asyncio.create_task(run_plex_library_update_service(
    refresh_time=max([5, config.plex.library_update_interval_minutes])))

number_of_players = 0


class RecommendationErrorType(enum.Enum):
    MISSING_PLEX_USERNAME = 1
    UNKNOWN_PLEX_USERNAME = 2
    SOMETHING_WENT_WRONG = 3


class RecommendationError:
    def __init__(self, error_type: RecommendationErrorType, message: str):
        self.error_type = error_type
        self.message = message


class Recommendation:
    def __init__(self, response: str, media_item, embed: discord.Embed = None):
        self.response = response
        self.embed = embed
        self.media_item = media_item


def valid_reaction(reaction_emoji: discord.PartialEmoji = None,
                   reaction_user_id: int = None,
                   reaction_message: discord.Message = None,
                   reaction_type: str = None,
                   valid_reaction_type: str = None,
                   valid_message: discord.Message = None,
                   valid_emojis: List[str] = None,
                   valid_user_ids: List[int] = None) -> bool:
    if valid_reaction_type and reaction_type != valid_reaction_type:
        return False
    if valid_message and reaction_message.id != valid_message.id:
        return False
    if valid_emojis and str(reaction_emoji) not in valid_emojis:
        return False
    if valid_user_ids and reaction_user_id not in valid_user_ids:
        return False
    return True


def error_and_analytics(error_message, function_name):
    error(error_message)
    analytics.event(event_category="Error",
                    event_action=function_name,
                    random_uuid_if_needed=True)


def make_recommendation(plex,
                        analytics: GoogleAnalytics,
                        trakt,
                        media_type: str,
                        unwatched: bool = False,
                        plex_username: str = None,
                        rating: float = None,
                        above: bool = True,
                        trakt_list_name: str = None) -> Union[Recommendation, RecommendationError]:
    recommendation = None
    if unwatched:
        if not plex_username:
            return RecommendationError(RecommendationErrorType.MISSING_PLEX_USERNAME,
                                       "Please provide a Plex username.")
        recommendation = picker.pick_unwatched(plex_connector=plex,
                                               username=plex_username,
                                               media_type=media_type,
                                               attempts=10)
        if isinstance(recommendation, int):
            if recommendation == picker.PickerFailureReason.PARAMETER_ERROR:
                return RecommendationError(RecommendationErrorType.UNKNOWN_PLEX_USERNAME,
                                           "I couldn't find that Plex username")
            elif recommendation == picker.PickerFailureReason.TO0_MANY_ATTEMPTS:
                return RecommendationError(RecommendationErrorType.UNKNOWN_PLEX_USERNAME,
                                           "Sorry, it took too long to find something for you")
    elif rating:
        recommendation = picker.pick_with_rating(plex_connector=plex,
                                                 media_type=media_type,
                                                 rating=rating,
                                                 above=above,
                                                 attempts=10)
        if isinstance(recommendation, int):
            if recommendation == picker.PickerFailureReason.TO0_MANY_ATTEMPTS:
                return RecommendationError(RecommendationErrorType.UNKNOWN_PLEX_USERNAME,
                                           "Sorry, it took too long to find something for you")
    elif trakt_list_name:
        recommendation = picker.pick_from_trakt_list(trakt_connector=trakt,
                                                     trakt_list_name=trakt_list_name,
                                                     plex_connector=plex,
                                                     attempts=10)
        if isinstance(recommendation, int):
            if recommendation == picker.PickerFailureReason.TO0_MANY_ATTEMPTS:
                return RecommendationError(RecommendationErrorType.UNKNOWN_PLEX_USERNAME,
                                           "Sorry, it took too long to find something for you")
    else:
        recommendation = picker.pick_random(plex_connector=plex,
                                            media_type=media_type)
    if not recommendation:
        return RecommendationError(RecommendationErrorType.SOMETHING_WENT_WRONG,
                                   "Something went wrong. Please try again later.")
    embed = discord_utils.make_embed(plex=plex,
                                     media_item=recommendation,
                                     analytics=analytics)
    return Recommendation(response=f"How about {recommendation.Title}?",
                          media_item=recommendation,
                          embed=embed)


async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
    emoji = payload.emoji
    user_id = payload.user_id
    reaction_type = "REACTION_ADD"

    if valid_reaction(reaction_message=None,
                      reaction_emoji=emoji,
                      reaction_user_id=user_id,
                      reaction_type=reaction_type,
                      valid_message=self.current_message,
                      valid_reaction_type=None,  # We already know it's the right type
                      valid_emojis=emoji_numbers[:number_of_players],
                      valid_user_ids=[config.discord.owner_id]):
        player_number = emoji_numbers.index(str(emoji))
        media_item = self.plex.get_full_media_item(content_media_item=media_item)
        if media_item:
            self.plex.play_media(player_number, media_item)


async def user_response(self, ctx, media_type: str, media_item: Content):
    if str(ctx.message.author.id) == str(self.config.discord.owner_id):
        global number_of_players
        response, number_of_players = self.plex.get_available_players(media_type=media_type)
        player_question = await ctx.send(response)
        if response:
            player_question = await ctx.send(response)
            try:
                for i in range(0, number_of_players - 1):
                    await player_question.add_reaction(emoji_numbers[i])

                # on_raw_reaction_add will handle the rest
            except asyncio.TimeoutError:
                await player_question.delete()


async def respond_with_recommendation(self,
                                      ctx: discord.ext.commands.Context,
                                      hold_message: str,
                                      media_type: str,
                                      recommendation_function: Callable) -> None:
    hold_message = await ctx.send(content=hold_message)
    async with ctx.typing():
        recommendation: Recommendation = recommendation_function()
    await hold_message.delete()
    if recommendation.embed is not None:
        await ctx.send(content=recommendation.response,
                       embed=recommendation.embed)
    else:
        await ctx.send(content=recommendation.response)
        self.analytics.event(event_category="Rec",
                             event_action="Successful new rec")
        await self.user_response(ctx=ctx,
                                 media_type=media_type,
                                 media_item=recommendation.media_item)


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
        if media_type.lower() not in self.plex.library_config.keys():
            accepted_types = "', '".join(self.plex.library_config.keys())
            await ctx.send(content=f"Please try again, indicating '{accepted_types}'")
        else:
            hold_message = f"Looking for {add_a_or_an(string=media_type)}..."
            return await self.respond_with_recommendation(ctx=ctx,
                                                          hold_message=hold_message,
                                                          media_type=media_type,
                                                          recommendation_function=lambda: make_recommendation(
                                                              plex=self.plex,
                                                              analytics=self.analytics,
                                                              trakt=self.trakt,
                                                              media_type=media_type,
                                                              unwatched=False,
                                                              plex_username=None)
                                                          )


@plex_rec.error
async def plex_rec_error(ctx, error_msg):
    error_and_analytics(error_message=error_msg,
                        function_name=inspect.currentframe().f_code.co_name)
    await ctx.send(content="Sorry, something went wrong while looking for a recommendation.")


@plex_rec.command()
async def plex_rec_new(self, ctx: commands.Context, plex_username: str):
    """
    Get a new movie, show or artist recommendation
    Include your Plex username
    """
    media_type = None
    for group in self.plex.library_config.keys():
        if group in ctx.message.content:
            media_type = group
            break
    if not media_type:
        accepted_types = "', '".join(self.plex.library_config.keys())
        await ctx.send(content=f"Please try again, indicating '{accepted_types}'")
    else:
        hold_message = f"Looking for a new {media_type}..."
        return await self.respond_with_recommendation(ctx=ctx,
                                                      hold_message=hold_message,
                                                      media_type=media_type,
                                                      recommendation_function=lambda: make_recommendation(
                                                          plex=self.plex,
                                                          analytics=self.analytics,
                                                          trakt=self.trakt,
                                                          media_type=media_type,
                                                          unwatched=True,
                                                          plex_username=plex_username)
                                                      )


@plex_rec_new.error
async def plex_rec_new_error(self, ctx, error_msg):
    error_and_analytics(error_message=error_msg,
                        function_name=inspect.currentframe().f_code.co_name)
    await ctx.send(content="Sorry, something went wrong while looking for a new recommendation.")


@plex_rec.command(name="above", aliases=['over', 'better'])
async def plex_rec_above(self, ctx: commands.Context, rating: Union[float, int]):
    """
    Get a movie or show above a certain IMDb rating (not music)
    Include your rating
    """
    media_type = None
    for group in self.plex.library_config.keys():
        if group in ctx.message.content:
            media_type = group
            break
    if not media_type or media_type not in ['movie', 'show']:
        await ctx.send(content=f"Sorry, this feature only works for movies and TV shows.")
    else:
        hold_message = f"Looking for {add_a_or_an(string=media_type)} that's rated at least {rating} on IMDb..."
        return await self.respond_with_recommendation(ctx=ctx,
                                                      hold_message=hold_message,
                                                      media_type=media_type,
                                                      recommendation_function=lambda: make_recommendation(
                                                          plex=self.plex,
                                                          analytics=self.analytics,
                                                          trakt=self.trakt,
                                                          media_type=media_type,
                                                          rating=float(rating),
                                                          above=True)
                                                      )


@plex_rec_above.error
async def plex_rec_above_error(self, ctx, error_msg):
    error_and_analytics(error_message=error_msg,
                        function_name=inspect.currentframe().f_code.co_name)
    await ctx.send(content="Sorry, something went wrong while looking for a new recommendation.")


@plex_rec.command(name="below", aliases=['under', 'worse'])
async def plex_rec_below(self, ctx: commands.Context, rating: Union[float, int]):
    """
    Get a movie or show below a certain IMDb rating (not music)
    Include your rating
    """
    media_type = None
    for group in self.plex.library_config.keys():
        if group in ctx.message.content:
            media_type = group
            break
    if not media_type or media_type not in ['movie', 'show']:
        await ctx.send(content=f"Sorry, this feature only works for movies and TV shows.")
    else:
        hold_message = f"Looking for {add_a_or_an(string=media_type)} that's rated less than {rating} on IMDb..."
        return await self.respond_with_recommendation(ctx=ctx,
                                                      hold_message=hold_message,
                                                      media_type=media_type,
                                                      recommendation_function=lambda: make_recommendation(
                                                          plex=self.plex,
                                                          analytics=self.analytics,
                                                          trakt=self.trakt,
                                                          media_type=media_type,
                                                          rating=float(rating),
                                                          above=False)
                                                      )


@plex_rec_below.error
async def plex_rec_below_error(self, ctx, error_msg):
    error_and_analytics(error_message=error_msg,
                        function_name=inspect.currentframe().f_code.co_name)
    await ctx.send(content="Sorry, something went wrong while looking for a new recommendation.")


@plex_rec.command(name="trakt")
async def plex_rec_trakt(self, ctx: commands.Context, *, list_name: str):
    """
    Get a movie or show from a specific Trakt.tv list

    Heads up: Large Trakt list may take a while to parse, and your request may time out.
    Once a choice is made from Trakt, the item is searched for in your Plex library. False matches are possible.
    """
    media_type = None
    for group in self.plex.library_config.keys():
        if group in ctx.message.content:
            media_type = group
            break
    if not media_type or media_type not in ['movie', 'show']:
        await ctx.send(content=f"Sorry, this feature only works for movies and TV shows.")
    else:
        hold_message = f"Looking for {add_a_or_an(string=media_type)} from the '{list_name}' list on Trakt.tv..."
        return await self.respond_with_recommendation(ctx=ctx,
                                                      hold_message=hold_message,
                                                      media_type=media_type,
                                                      recommendation_function=lambda: make_recommendation(
                                                          plex=self.plex,
                                                          analytics=self.analytics,
                                                          trakt=self.trakt,
                                                          media_type=media_type,
                                                          trakt_list_name=list_name)
                                                      )


@plex_rec_trakt.error
async def plex_rec_trakt_error(self, ctx, error_msg):
    error_and_analytics(error_message=error_msg,
                        function_name=inspect.currentframe().f_code.co_name)
    await ctx.send(content="Sorry, something went wrong while looking for a new recommendation.")
