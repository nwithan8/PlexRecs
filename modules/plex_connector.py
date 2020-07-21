from plexapi.server import PlexServer
from plexapi import exceptions as plex_exceptions
from progress.bar import Bar
from modules.logs import *
import modules.tautulli_connector as tautulli


class SmallMediaItem:
    def __init__(self, title, year, ratingKey, librarySectionID, mediaType):
        self.title = title
        self.year = year
        self.ratingKey = ratingKey
        self.librarySectionID = librarySectionID
        self.type = mediaType


def search_for_item(library_section, title, year):
    return library_section.search(title=title, year=[year])


class PlexConnector:
    def __init__(self, url, token, server_id, server_name, library_list, tautulli_url, tautulli_key):
        self.url = url
        self.token = token
        self.server_id = server_id
        self.name = server_name
        self.server = PlexServer(self.url, self.token)
        info("Connected to Plex.")
        self.tautulli = None
        self.tautulli_url = tautulli_url
        self.tautulli_key = tautulli_key
        self.make_tautulli_connector()
        info("Connected to Tautulli.")
        self.libraries = {}
        self.initialize_library(library_list=library_list)
        self.owner_players = []

    def make_tautulli_connector(self):
        self.tautulli = tautulli.TautulliConnector(url=self.tautulli_url, api_key=self.tautulli_key)

    def initialize_library(self, library_list):
        for name, numbers in library_list.items():
            self.libraries[name] = [numbers, []]
        info(f"Libraries: {self.libraries}")

    def clean_libraries(self):
        for groupName, items in self.libraries.items():
            items[1].clear()

    def make_library(self, libraryName, attempts: int = 0):
        try:
            if not self.libraries[libraryName][1]:
                for libraryNumber in self.libraries[libraryName][0]:
                    json_data = self.tautulli.api_call_get("get_library", f"section_id={libraryNumber}")
                    if json_data:
                        count = json_data['response']['data']['count']
                        bar = Bar(f'Loading {libraryName} (Library section {libraryNumber})', max=int(count))
                        librarySection = self.server.library.sectionByID(f"{libraryNumber}")
                        for item in librarySection.all():
                            try:
                                self.libraries[libraryName][1].append(
                                    SmallMediaItem(title=item.title,
                                                   year=(None if librarySection.type == 'artist' else item.year),
                                                   ratingKey=item.ratingKey, librarySectionID=item.librarySectionID,
                                                   mediaType=item.type))
                            except plex_exceptions.PlexApiException as e:
                                error(f"Could not create SmallMediaItem for Plex library item: {e}")
                            bar.next()
                        bar.finish()
                        return True
                    else:
                        error(f"Could not get JSON data to build {libraryName} library.")
        except KeyError as e:
            error(f"Could not get section {libraryNumber} ({libraryName}) from the Plex Server: {e}")
        except plex_exceptions.PlexApiException as e:
            error(f"Could not create SmallMediaItem from Plex library item: {e}")
        except Exception as e:
            error(f'Error in makeLibrary: {e}')
            if attempts < 5:  # for generic errors, retry making the library
                return self.make_library(libraryName=libraryName, attempts=attempts + 1)
        return False

    def make_libraries(self):
        if not self.tautulli:
            self.make_tautulli_connector()
        self.clean_libraries()
        for groupName in self.libraries.keys():
            self.make_library(libraryName=groupName)

    def get_user_history(self, username, sectionIDs):
        return self.tautulli.get_user_history(self, username, sectionIDs)

    def get_available_players(self, mediaType):
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
        return f'{players_list}\nReact with which player you want to start this {mediaType} on.', num

    def playMedia(self, playerNumber, mediaItem):
        self.owner_players[playerNumber].goToMedia(mediaItem)

    def get_library_section(self, section_id):
        return self.server.library.sectionByID(f"{section_id}")

    def getFullMediaItem(self, mediaItem, match_keys: bool = True):
        librarySection = self.get_library_section(section_id=mediaItem.librarySectionID)
        for item in search_for_item(library_section=librarySection, title=mediaItem.title, year=mediaItem.year):
            if match_keys:
                if item.ratingKey == mediaItem.ratingKey:
                    return item
            else:
                return item
        return None

    def is_on_plex(self, title, year, section_id=None, section_name=None, exact_match: bool = False):
        sections_ids_to_check = []
        if section_id:
            sections_ids_to_check.append(section_id)
        elif section_name:
            section = self.server.library.section(title=section_name)
            if section:
                sections_ids_to_check.append(section.key)
        if not sections_ids_to_check:
            for name, ids in self.libraries.items():
                for libraryNumber in ids[0]:
                    sections_ids_to_check.append(libraryNumber)
        for s_id in sections_ids_to_check:
            temp_media_item = SmallMediaItem(title=title, year=year, ratingKey=None,
                                             librarySectionID=s_id, mediaType=None)
            possible_match = self.getFullMediaItem(mediaItem=temp_media_item, match_keys=exact_match)
            if possible_match:
                return possible_match
        return False
