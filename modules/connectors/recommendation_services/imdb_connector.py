import imdb

from modules.analytics import GoogleAnalytics
from modules.logs import *

im = imdb.IMDb()


def get_imdb_item(title: str, analytics: GoogleAnalytics):
    try:
        search_results = im.search_for_title(title)
        if search_results:
            return im.get_title(search_results[0].imdb_id)
    except Exception as e:
        error(f"Could not get IMDb item: {e}")
        analytics.event(event_category="Error", event_action='get_imdb_item', random_uuid_if_needed=True)
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
