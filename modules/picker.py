import random
from typing import List

import modules.imdb_connector as imdb
from modules.logs import *
from modules.plex_connector import PlexConnector
from modules.trakt_connector import TraktConnector


def _rating_is_correct(imdb_item, rating: float, above: bool = True):
    if not imdb_item.rating:
        return False
    elif above and imdb_item.rating < rating:  # want above and temp_choice is not above rating
        return False
    elif not above and imdb_item.rating > rating:  # want below and temp_choice is not below rating
        return False
    return True


def pick_with_rating(plex_connector: PlexConnector, media_type: str, rating: float, above: bool = True,
                     attempts: int = 10):
    attempt_counter = 0
    while attempt_counter < attempts:
        choice = plex_connector.get_random_media_item(media_type=media_type)
        imdb_item = imdb.get_imdb_item(choice.Title, choice.Year)
        if _rating_is_correct(imdb_item=imdb_item, rating=rating, above=above):
            return choice
        attempt_counter += 1
    return "Too many attempts"


def pick_unwatched(plex_connector: PlexConnector, username: str, media_type: str, attempts: int = 10):
    """
    Keep picking until something is unwatched
    :param media_type:
    :param username:
    :param plex_connector:
    :return: SmallMediaItem object
    """
    history = plex_connector.get_user_history(username=username,
                                              section_ids=plex_connector.get_section_ids_for_media_type(media_type))
    if history == "Error":
        return False

    attempt_counter = 0
    while attempt_counter < attempts:  # give up after ten failures
        choice = plex_connector.get_random_media_item(media_type=media_type)
        if choice.Title not in history:
            return choice
        attempt_counter += 1
    return "Too many attempts"


def pick_from_trakt_list(trakt_connector: TraktConnector, trakt_list_name: str, plex_connector: PlexConnector,
                         attempts: int = 5):
    trakt_list = trakt_connector.get_list_items(list_name=trakt_list_name)
    attempt_counter = 0
    while attempt_counter < attempts:  # give up after five failures
        trakt_choice = random.choice(trakt_list)
        info(f"Choice from Trakt: {trakt_choice.title}, {trakt_choice.year}")
        external_ids = imdb.build_ids_dict(trakt_choice.ids['ids'])
        plex_equivalent = plex_connector.is_on_plex(title=trakt_choice.title, year=trakt_choice.year,
                                                    external_ids=external_ids, match_rating_keys=False)
        if plex_equivalent:
            info(f"Match from Plex: {plex_equivalent.title}, {plex_equivalent.year}")
            return plex_equivalent
        info(f"Couldn't find {trakt_choice.title} on Plex. Trying a different item...")
        attempt_counter += 1
    return "Too many attempts"


def pick_random(plex_connector: PlexConnector, media_type: str):
    return plex_connector.get_random_media_item(media_type=media_type)
