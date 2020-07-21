from imdbpie import ImdbFacade
from modules.logs import *

imdb = ImdbFacade()


def get_imdb_item(title):
    try:
        search_results = imdb.search_for_title(title)
        if search_results:
            return imdb.get_title(search_results[0].imdb_id)
    except Exception as e:
        error(f"Could not get IMDb item: {e}")
    return None


def build_ids_dict(ids):
    ids_dict = {}
    if ids.get('imdb'):
        ids_dict['imdb'] = ids['imdb']
    if ids.get('tvdb'):
        ids_dict['thetvdb'] = ids['tvdb']
    if ids.get('tmdb'):
        ids_dict['themoviedb'] = ids['tmdb']
    return ids_dict
