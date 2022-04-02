from plexapi import exceptions as plex_exceptions
from plexapi.server import PlexServer
from progress.bar import Bar

import modules.tautulli_connector as tautulli
from modules.logs import *


class SmallMediaItem:
    def __init__(self, title, year, rating_key, library_section_id, media_type, external_ids=None):
        self.title = title
        self.year = year
        self.ratingKey = rating_key
        self.librarySectionID = library_section_id
        self.type = media_type
        self.external_ids = external_ids


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


class PlexConnector:
    def __init__(self, url, token, server_name, library_list, tautulli_url, tautulli_key, analytics):
        self.url = url
        self.token = token
        self.name = server_name
        self.server = PlexServer(self.url, self.token)
        self.server_id = self.server.machineIdentifier
        self.analytics = analytics
        info("Connected to Plex.")
        self.tautulli = None
        self.tautulli_url = tautulli_url
        self.tautulli_key = tautulli_key
        self.make_tautulli_connector()
        info("Connected to Tautulli.")
        self.libraries = {}
        self.initialize_library(library_list=library_list)
        self.owner_players = []

    def _error_and_analytics(self, error_message, function_name):
        error(error_message)
        self.analytics.event(event_category="Error", event_action=function_name, random_uuid_if_needed=True)

    def make_tautulli_connector(self):
        self.tautulli = tautulli.TautulliConnector(url=self.tautulli_url, api_key=self.tautulli_key,
                                                   analytics=self.analytics)

    def initialize_library(self, library_list):
        for name, numbers in library_list.items():
            self.libraries[name] = [numbers, []]
        info(f"Libraries: {self.libraries}")

    def clean_libraries(self):
        for groupName, items in self.libraries.items():
            items[1].clear()

    def make_library(self, library_name, attempts: int = 0):
        try:
            if not self.libraries[library_name][1]:
                for library_number in self.libraries[library_name][0]:
                    json_data = self.tautulli.api_call_get("get_library", f"section_id={library_number}")
                    if json_data:
                        count = json_data['response']['data']['count']
                        bar = Bar(f'Loading {library_name} (Library section {library_number})', max=int(count))
                        library_section = self.server.library.sectionByID(f"{library_number}")
                        for item in library_section.all():
                            try:
                                self.libraries[library_name][1].append(
                                    SmallMediaItem(title=item.title,
                                                   year=(None if library_section.type == 'artist' else item.year),
                                                   rating_key=item.ratingKey, library_section_id=item.librarySectionID,
                                                   media_type=item.type))
                            except plex_exceptions.PlexApiException as e:
                                self._error_and_analytics(
                                    error_message=f"Could not create Smallmedia_item for Plex library item: {e}",
                                    function_name='make_library (smallmedia_item internal)')
                            bar.next()
                        bar.finish()
                        return True
                    else:
                        self._error_and_analytics(
                            error_message=f"Could not get JSON data to build {library_name} library.",
                            function_name='make_library (JSONError)')
        except KeyError as e:
            self._error_and_analytics(
                error_message=f"Could not get section {library_number} ({library_name}) from the Plex Server: {e}",
                function_name='make_library (KeyError)')
        except plex_exceptions.PlexApiException as e:
            self._error_and_analytics(error_message=f"Could not create Smallmedia_item from Plex library item: {e}",
                                      function_name='make_library (PlexApiException)')
        except Exception as e:
            self._error_and_analytics(error_message=f'Error in makeLibrary: {e}',
                                      function_name='make_library (general)')
            if attempts < 5:  # for generic errors, retry making the library
                return self.make_library(library_name=library_name, attempts=attempts + 1)
        return False

    def make_libraries(self):
        if not self.tautulli:
            self.make_tautulli_connector()
        self.clean_libraries()
        for groupName in self.libraries.keys():
            self.make_library(library_name=groupName)

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

    def get_full_media_item(self, media_item, external_ids=None, match_keys: bool = True):
        if external_ids is None:
            external_ids = []
        library_section = self.get_library_section(section_id=media_item.librarySectionID)
        for item in search_for_item(library_section=library_section, title=media_item.title, year=media_item.year,
                                    external_ids=external_ids):
            if match_keys:
                if item.ratingKey == media_item.ratingKey:
                    return item
            else:
                return item  # go with the first item in the list
        return None

    def get_server_id(self):
        return self.server.machineIdentifier

    def is_on_plex(self, title, year, external_ids=None, section_id=None, section_name=None,
                   match_rating_keys: bool = False):
        sections_ids_to_check = []
        if section_id:
            sections_ids_to_check.append(section_id)
        elif section_name:
            section = self.server.library.section(title=section_name)
            if section:
                sections_ids_to_check.append(section.key)
        if not sections_ids_to_check:
            for name, ids in self.libraries.items():
                for library_number in ids[0]:
                    sections_ids_to_check.append(library_number)
        for s_id in sections_ids_to_check:
            temp_media_item = SmallMediaItem(title=title, year=year, rating_key=None,
                                             library_section_id=s_id, media_type=None, external_ids=external_ids)
            possible_match = self.get_full_media_item(media_item=temp_media_item, match_keys=match_rating_keys)
            if possible_match:
                return possible_match
        return False
