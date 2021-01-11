from imdbpie import ImdbFacade
from modules.logs import *

imdb = ImdbFacade()


def get_imdb_item(title, analytics):
    try:
        search_results = imdb.search_for_title(title)
        if search_results:
            return imdb.get_title(search_results[0].imdb_id)
    except Exception as e:
        error(f"Could not get IMDb item: {e}")
        analytics.event(event_category="Error", event_action='get_imdb_item', random_uuid_if_needed=True)
    return None


def check_score(plex_item, rating: float, analytics, above: bool = True):
    imdb_item = get_imdb_item(plex_item.title, analytics=analytics)
    if not imdb_item:
        return False
    if not imdb_item.rating:
        return False
    elif above and imdb_item.rating < rating:  # want above and temp_choice is not above rating
        return False
    elif not above and imdb_item.rating > rating:  # want below and temp_choice is not below rating
        return False
    return True



def build_ids_dict(ids):
    ids_dict = {}
    if ids.get('imdb'):
        ids_dict['imdb'] = ids['imdb']
    if ids.get('tvdb'):
        ids_dict['thetvdb'] = ids['tvdb']
    if ids.get('tmdb'):
        ids_dict['themoviedb'] = ids['tmdb']
    return ids_dict
