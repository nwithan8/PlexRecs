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
