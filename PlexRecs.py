import asyncio
import discord
from discord.ext import commands, tasks
import credentials
import sys
from typing import Union, List

import info as bot_info
from modules.logs import *
import modules.plex_connector as plex_connector
import modules.trakt_connector as trakt_connector
import modules.imdb_connector as imdb_connector
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


def build_filters(filters: List[str]):
    imdb_filter = None
    new_filter = None
    trakt_filter = None
    search_filters = {}
    for i in range(0, len(filters), 2):
        key = filters[i]
        value = filters[i + 1]
        if key == 'new':
            new_filter = [key, value]  # ['new', 'plex_username']
        elif key == 'imdb':
            imdb_filter = [key, value]  # ['imdb', '+65']
        elif key == 'trakt':
            trakt_filter = [key, value]  # ['trakt', 'list_name']
        else:
            search_filters[key] = value
    return {
        'imdb': imdb_filter,
        'tautulli': new_filter,
        'trakt': trakt_filter,
        'plex': search_filters
    }


def make_holding_message(media_type: str, filters: dict = None):
    message = f"Looking for {discord_utils.a_versus_an(word=media_type)} {media_type}..."
    if filters:
        message += "\nFilters:"
        for k, v in filters.items():
            if v:
                message += f"\n- {k}: {v}"
    return message


def error_and_analytics(error_message, function_name):
    error(error_message)
    analytics.event(event_category="Error",
                    event_action=function_name,
                    random_uuid_if_needed=True)


def find_recommendation(media_type: str,
                        filters: dict = None):
    if not filters:  # no filter, just pull a random one from pre-stored
        return picker.pick_random(a_list=plex.libraries[media_type][1])

    elif filters.get('trakt'):
        # Ignore all other filters, too difficult
        if media_type not in ['movie', 'show']:
            return picker.Error(message=f"Sorry, this feature only works for movies and TV shows.")

        trakt_list = trakt.get_list_items(list_name=filters['trakt'][1])
        return picker.pick_from_trakt_list(trakt_list=trakt_list, plex_instance=plex)

    else:  # going to have to hit the Plex API to filter it
        filtered_from_search = plex.libraries[media_type][1]  # start with the pre-stored

        if filters.get('plex'):  # replace with API if need to filter from Plex
            filtered_from_search = []
            library_sections = [plex.get_library_section(section_id=section_id) for section_id in
                                plex.libraries[media_type][0]]
            for section in library_sections:
                temp_results = plex_connector.search(library_section=section, **(filters['plex']))
                for item in temp_results:
                    filtered_from_search.append(item)

        if not filtered_from_search:
            return picker.Error(message="There are no Plex items that match those filters.")

        tautulli_history = []
        if filters.get('tautulli'):  # get user history to check for a new item
            tautulli_history = plex.get_user_history(username=filters['tautulli'][1],
                                                     sections_ids=plex.libraries[media_type][0])

        passes_all_filters = False
        retries = 0
        random_item = None

        while not passes_all_filters:

            if retries > 10:
                return random_item

            if tautulli_history:
                random_item = picker.pick_unwatched(history=tautulli_history, media_list=filtered_from_search)
                if type(random_item) == picker.Error:
                    return random_item
            else:
                random_item = picker.pick_random(a_list=filtered_from_search)

            if filters.get('imdb'):
                above = True
                score = float(filters['imdb'][1][1:])
                if filters['imdb'][1][0] == '-':
                    above = False
                if imdb_connector.check_score(plex_item=random_item, rating=score, above=above, analytics=analytics):
                    return random_item
            else:
                return random_item

            retries += 1

        return random_item


def make_recommendation(media_type,
                        filters: dict = None):
    recommended_item = find_recommendation(media_type=media_type, filters=filters)

    if type(recommended_item) == picker.Error:
        return recommended_item.message, None, None

    embed = discord_utils.make_embed(plex=plex, analytics=analytics, media_item=recommended_item)
    return f"How about {recommended_item.title}?", embed, recommended_item


class PlexRecs(commands.Cog):

    async def user_response(self, ctx, media_type, media_item):
        if str(ctx.message.author.id) == str(credentials.OWNER_DISCORD_ID):
            response, num_of_players = plex.get_available_players(media_type=media_type)
            if response:
                ask_about_player = True
                while ask_about_player:
                    try:
                        def check(react, react_user, num_players):
                            return str(react.emoji) in emoji_numbers[:num_of_players] \
                                   and react_user.id == credentials.OWNER_DISCORD_ID

                        player_question = await ctx.send(response)
                        for i in range(0, num_of_players - 1):
                            await player_question.add_reaction(emoji_numbers[i])
                        reaction, user = await self.bot.wait_for('reaction_add',
                                                                 timeout=60.0,
                                                                 check=check)
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
    async def makeLibraries(self):
        plex.make_libraries()

    @commands.command(name="recommend", aliases=['suggest', 'rec', 'sugg'], pass_context=True)
    async def plex_rec(self, ctx: commands.Context, mediaType: str, *, filters: str = None):
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
        if filters:
            filters = filters.split()
            filters = build_filters(filters=filters)
        else:
            filters = {}

        info(filters)

        holding_message = await ctx.send(make_holding_message(media_type=mediaType, filters=filters))

        async with ctx.typing():
            message, embed, recommended_item = make_recommendation(media_type=mediaType, filters=filters)

        await holding_message.delete()

        if embed is not None:
            await ctx.send(message, embed=embed)
        else:
            await ctx.send(message)

        analytics.event(event_category="Rec", event_action="Successful rec")

        if recommended_item and type(recommended_item) is not picker.Error:
            await self.user_response(ctx=ctx, media_type=mediaType, media_item=recommended_item)

    @plex_rec.error
    async def plex_rec_error(self, ctx, error_msg):
        error_and_analytics(error_message=error_msg, function_name='plex_rec')
        await ctx.send("Sorry, something went wrong while looking for a recommendation.")

    def __init__(self, bot):
        print(bot_info.COPYRIGHT_MESSAGE)
        self.bot = bot
        analytics.event(event_category="Platform",
                        event_action=sys.platform)
        info("Updating Plex libraries...")
        self.makeLibraries.start()


def setup(bot):
    bot.add_cog(PlexRecs(bot))
