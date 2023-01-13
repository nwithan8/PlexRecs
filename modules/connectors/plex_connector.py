from typing import List, Union

import discord
from plexapi.library import LibrarySection
from plexapi.server import PlexServer
from progress.bar import Bar

import modules.connectors.tautulli_connector as tautulli
import modules.logs as logging
from modules.analytics import GoogleAnalytics
from modules.config_parser import PlexConfig
from modules.library_database import PlexContentDatabase, Content


def get_possible_matching_items(library_section, title, year, external_ids: List[str] = None) -> List:
    matches = []
    if external_ids:
        if 'guid' not in library_section.ALLOWED_FILTERS:
            library_section.ALLOWED_FILTERS += ('guid',)
        for e_id in external_ids:
            for item in library_section.search(guid=f"{e_id}"):
                if item not in matches:
                    matches.append(item)
    else:
        matches = library_section.search(title=title, year=[year])
    return matches


def get_possible_section_filters(library_section: LibrarySection) -> List:
    return library_section.ALLOWED_FILTERS


def _build_filters(library_section: LibrarySection, **kwargs):
    available_filters = [item.key for item in library_section.filterFields()]
    final_filters = {}
    for k, v in kwargs.items():
        if k in available_filters and v:
            final_filters[k] = v
    return final_filters


def valid_reaction(reaction: discord.Reaction, user: discord.User, on_message: discord.Message = None, ) -> bool:
    return reaction.message.author == user and reaction.message.channel == user.dm_channel


def _contains_keywords(item, keywords: list) -> bool:
    """
    Any one of multiple keywords exists in title or description?
    :param item:
    :type item:
    :param keywords:
    :type keywords:
    :return:
    :rtype:
    """
    for keyword in keywords:
        if keyword.lower() in item.summary.lower():
            return True
        elif keyword.lower() in item.title.lower():
            return True
    return False


def search(library_section: LibrarySection,
           **kwargs):
    proper_filters = _build_filters(library_section=library_section, **kwargs)
    if kwargs.get('external_id'):
        # TODO Fix this
        if 'guid' not in library_section.ALLOWED_FILTERS:
            library_section.ALLOWED_FILTERS += ('guid',)
        for source_name, e_id in kwargs.get('external_id').items():
            proper_filters['guid'] = f"{source_name}://{e_id}"
    search_results = library_section.search(**proper_filters)
    if kwargs.get('keywords'):
        results_with_keyword = []
        for item in search_results:
            if _contains_keywords(item=item, keywords=kwargs.get('keywords')):
                results_with_keyword.append(item)
        return results_with_keyword
    return search_results


class SmallMediaItem:
    def __init__(self, title, year, rating_key, library_section_id, media_type, external_ids: List[str] = None):
        self.title = title
        self.year = year
        self.rating_key = rating_key
        self.library_section_id = library_section_id
        self.type = media_type
        self.external_ids = external_ids

    def add_to_database(self, database: PlexContentDatabase):
        database.add_content(title=self.title, year=self.year, rating_key=self.rating_key,
                             library_section_id=self.library_section_id, media_type=self.type,
                             external_ids=self.external_ids)


class PlexConnector:

    _analytics: GoogleAnalytics

    def __init__(self,
                 config: PlexConfig,
                 analytics: GoogleAnalytics):
        self._analytics = analytics

        self.name = server_name
        self.server = PlexServer(baseurl=url, token=token)
        self.library_config = library_list
        self.tautulli = tautulli.TautulliConnector(url=tautulli_url,
                                                   api_key=tautulli_key,
                                                   analytics=analytics)
        self.database = database
        self.owner_players = []

    def get_section_ids_for_media_type(self, media_type: str) -> List[int]:
        if media_type not in self.library_config.keys():
            return []
        return self.library_config[media_type]

    def _error_and_analytics(self, error_message: str, function_name: str):
        logging.error(message=error_message)
        self._analytics.event(event_category="Error", event_action=function_name, random_uuid_if_needed=True)

    def initialize_libraries(self) -> None:
        for name, numbers in self.library_config.items():
            if numbers:
                for number in numbers:
                    self.database.add_library(name=name, plex_id=number)
                    logging.info(f"Added library {name} with number {number} to database.")

    def get_random_media_item(self, library_id: int = None, media_type: str = None) -> Content:
        if library_id:
            return self.database.get_random_contents_for_library(library_section_id=library_id)[0]
        else:
            return self.database.get_random_contents_of_type(media_type=media_type)[0]

    def clean_libraries(self) -> None:
        self.database.purge()

    async def _populate_library(self, library_name: str):
        if library_name not in self.library_config.keys():
            return
        for library_number in self.library_config[library_name]:
            tautulli_data = self.tautulli.get_library(library_number=library_number)
            if not tautulli_data:
                self._error_and_analytics(f"Could not find library {library_number} on Tautulli", "_populate_library")
                continue
            bar = Bar('Populating library', max=tautulli_data.count)
            library_section = self.server.library.sectionByID(library_number)
            if not library_section:
                self._error_and_analytics(f"Could not find library {library_number} on Plex", "_populate_library")
                continue
            for item in library_section.all():
                external_ids = []
                try:
                    external_ids = [guid.id for guid in item.guids]
                except AttributeError:
                    pass
                small_media_item = SmallMediaItem(title=item.title,
                                                  year=(None if library_section.type == 'artist' else item.year),
                                                  rating_key=item.ratingKey,
                                                  library_section_id=item.librarySectionID,
                                                  media_type=item.type,
                                                  external_ids=external_ids)
                small_media_item.add_to_database(database=self.database)
                bar.next()
            bar.finish()

    async def populate_libraries(self):
        self.clean_libraries()
        for group_name in self.library_config.keys():
            await self._populate_library(library_name=group_name)

    def get_user_history(self, username: str, section_ids: List[int]) -> Union[List[str], None]:
        return self.tautulli.get_user_history(username=username, section_ids=section_ids)

    def get_available_players(self, media_type):
        self.owner_players = []
        players = self.server.clients()
        if not players:
            return None, 0
        num = 0
        players_list = ""
        for player in players[:5]:
            num = num + 1
            players_list += f'\n{num}:{player.title}'
            self.owner_players.append(player)
        return f'{players_list}\nReact with which player you want to start this {media_type} on.', num

    def play_media(self, player_number, media_item):
        self.owner_players[player_number].goToMedia(media_item)

    def get_library_section(self, section_id):
        return self.server.library.sectionByID(f"{section_id}")

    def get_full_media_item(self, content_media_item: Content = None, small_media_item: SmallMediaItem = None,
                            match_keys: bool = True):
        library_section = self.get_library_section(
            section_id=content_media_item.LibraryID if content_media_item else small_media_item.library_section_id)
        if not library_section:
            return None
        for item in get_possible_matching_items(library_section=library_section,
                                                title=content_media_item.Title if content_media_item else small_media_item.title,
                                                year=content_media_item.Year if content_media_item else None,
                                                external_ids=self.database.get_external_ids_for_content(
                                                    content_id=content_media_item.ID) if content_media_item else small_media_item.external_ids
                                                ):
            if match_keys:
                if item.ratingKey == (
                        content_media_item.RatingKey if content_media_item else small_media_item.rating_key):
                    return item
            else:
                return item  # go with the first item in the list
        return None

    @property
    def server_id(self):
        return self.server.machineIdentifier

    def is_on_plex(self, title: str, year: int, external_ids: List[str] = None, section_id: int = None,
                   section_name: str = None, match_rating_keys: bool = False):
        sections_ids_to_check = []
        if section_id:
            sections_ids_to_check.append(section_id)
        elif section_name:
            section = self.server.library.section(title=section_name)
            if section:
                sections_ids_to_check.append(section.key)
        if not sections_ids_to_check:
            for _, numbers in self.library_config.items():
                for number in numbers:
                    sections_ids_to_check.append(number)
        for s_id in sections_ids_to_check:
            temp_media_item = SmallMediaItem(title=title, year=year, rating_key=None,
                                             library_section_id=s_id, media_type=None, external_ids=external_ids)
            possible_match = self.get_full_media_item(small_media_item=temp_media_item, match_keys=match_rating_keys)
            if possible_match:
                return possible_match
        return False
