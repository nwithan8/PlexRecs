import random
import modules.imdb_connector as imdb
from modules.logs import *


def pick_random(aList):
    return random.choice(aList)


def rating_is_correct(item, rating: float, above: bool = True):
    if not item.rating:
        return False
    elif above and item.rating < rating:  # want above and temp_choice is not above rating
        return False
    elif not above and item.rating > rating:  # want below and temp_choice is not below rating
        return False
    return True


def pickWithRating(aList, rating: float, above: bool = True, attempts: int = 0):
    temp_choice = pick_random(aList)
    imdb_item = imdb.get_imdb_item(temp_choice.title)
    info(f"IMDb item: {imdb_item.title}; Rating: {imdb_item.rating}")
    if not rating_is_correct(item=imdb_item, rating=rating, above=above):
        if attempts > 10:  # give up after ten failures
            return "Too many attempts"
        return pickWithRating(aList=aList, rating=rating, above=above, attempts=attempts + 1)
    return temp_choice


def pick_unwatched(history, mediaList, attempts: int = 0):
    """
    Keep picking until something is unwatched
    :param attempts:
    :param history:
    :param mediaList: Movies list, Shows list or Artists list
    :return: SmallMediaItem object
    """
    if history == "Error":
        return False
    choice = pick_random(mediaList)
    if choice.title in history:
        if attempts > 10:  # give up after ten failures
            return "Too many attempts"
        return pickUnwatched(history, mediaList, attempts=attempts + 1)
    return choice
