import random

import modules.imdb_connector as imdb
from modules.logs import *


def pick_random(a_list):
    return random.choice(a_list)


def rating_is_correct(item, rating: float, above: bool = True):
    if not item.rating:
        return False
    elif above and item.rating < rating:  # want above and temp_choice is not above rating
        return False
    elif not above and item.rating > rating:  # want below and temp_choice is not below rating
        return False
    return True


def pick_with_rating(a_list, rating: float, above: bool = True, attempts: int = 0):
    temp_choice = pick_random(a_list)
    imdb_item = imdb.get_imdb_item(temp_choice.title)
    info(f"IMDb item: {imdb_item.title}; Rating: {imdb_item.rating}")
    if not rating_is_correct(item=imdb_item, rating=rating, above=above):
        if attempts > 10:  # give up after ten failures
            return "Too many attempts"
        return pick_with_rating(a_list=a_list, rating=rating, above=above, attempts=attempts + 1)
    return temp_choice


def pick_unwatched(history, media_list, attempts: int = 0):
    """
    Keep picking until something is unwatched
    :param attempts:
    :param history:
    :param media_list: Movies list, Shows list or Artists list
    :return: SmallMediaItem object
    """
    if history == "Error":
        return False
    choice = pick_random(media_list)
    if choice.title in history:
        if attempts > 10:  # give up after ten failures
            return "Too many attempts"
        return pick_unwatched(history, media_list, attempts=attempts + 1)
    return choice


def pick_from_trakt_list(trakt_list, plex_instance, genre: str = None, rating: float = None, above: bool = True,
                         attempts: int = 0):
    temp_choice = pick_random(trakt_list)
    info(f"Choice from Trakt: {temp_choice.title}, {temp_choice.year}")
    external_ids = imdb.build_ids_dict(temp_choice.ids['ids'])
    plex_equivalent = plex_instance.is_on_plex(title=temp_choice.title, year=temp_choice.year,
                                               external_ids=external_ids, match_rating_keys=False)
    if plex_equivalent:
        info(f"Match from Plex: {plex_equivalent.title}, {plex_equivalent.year}")
        return plex_equivalent
    if attempts < 5:
        info(f"Couldn't find {temp_choice.title} on Plex. Trying a different item...")
        pick_from_trakt_list(trakt_list=trakt_list, plex_instance=plex_instance, genre=genre, rating=rating,
                             above=above, attempts=attempts + 1)
    return "Too many attempts"
