from typing import List

from plexapi.server import PlexServer
from progress.bar import Bar

import modules.tautulli_connector as tautulli
from modules.analytics import GoogleAnalytics
from modules.library_database import PlexContentDatabase
from modules.logs import *


def search_for_item(library_section, title, year, external_ids=None):
    matches = []
    if external_ids:
        if 'guid' not in library_section.ALLOWED_FILTERS:
            library_section.ALLOWED_FILTERS += ('guid',)
        for source_name, e_id in external_ids.items():
            for item in library_section.search(guid=f"{source_name}://{e_id}"):
                if item not in matches:
                    matches.append(item)
    else:
        matches = library_section.search(title=title, year=[year])
    return matches


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
    def __init__(self, url: str, token: str, server_name: str, library_list: dict, tautulli_url: str, tautulli_key: str,
                 analytics: GoogleAnalytics, database: PlexContentDatabase):
        self.name = server_name
        self.server = PlexServer(baseurl=url, token=token)
        self.analytics = analytics
        info("Connected to Plex.")
        self.library_config = library_list
        self.tautulli = tautulli.TautulliConnector(url=tautulli_url, api_key=tautulli_key,
                                                   analytics=analytics)
        info("Connected to Tautulli.")
        self.database = database
        info("Connected to database.")
        self.initialize_libraries()
        self.owner_players = []

    def get_section_ids_for_media_type(self, media_type: str):
        if media_type not in self.library_config.keys():
            return []
        return self.library_config[media_type]

    def _error_and_analytics(self, error_message: str, function_name: str):
        error(message=error_message)
        self.analytics.event(event_category="Error", event_action=function_name, random_uuid_if_needed=True)

    def initialize_libraries(self):
        for name, numbers in self.library_config.items():
            for number in numbers:
                self.database.add_library(name=name, plex_id=number)
                info(f"Added library {name} with number {number} to database.")

    def get_random_media_item(self, library_id: int = None, media_type: str = None):
        if library_id:
            return self.database.get_random_content_for_library(library_section_id=library_id)
        else:
            return self.database.get_random_content_of_type(media_type=media_type)

    def clean_libraries(self):
        self.database.purge()

    def _populate_library(self, library_name: str):
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
                small_media_item = SmallMediaItem(title=item.title,
                                                  year=(None if library_section.type == 'artist' else item.year),
                                                  rating_key=item.ratingKey,
                                                  library_section_id=item.librarySectionID,
                                                  media_type=item.type)
                small_media_item.add_to_database(database=self.database)
                bar.next()
            bar.finish()

    def populate_libraries(self):
        self.clean_libraries()
        for group_name in self.library_config.keys():
            self._populate_library(library_name=group_name)

    def get_user_history(self, username, section_ids):
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

    def get_full_media_item(self, media_item: SmallMediaItem, external_ids: List[str] = None, match_keys: bool = True):
        if external_ids is None:
            external_ids = []
        library_section = self.get_library_section(section_id=media_item.library_section_id)
        if not library_section:
            return None
        for item in search_for_item(library_section=library_section, title=media_item.title, year=media_item.year,
                                    external_ids=external_ids):
            if match_keys:
                if item.ratingKey == media_item.rating_key:
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
            possible_match = self.get_full_media_item(media_item=temp_media_item, match_keys=match_rating_keys)
            if possible_match:
                return possible_match
        return False
