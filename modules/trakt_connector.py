from modules.logs import *
import trakt
import trakt.core
from trakt.users import User


def sign_in(username: str, client_id: str = None, client_secret: str = None, application_id=None,
            stay_logged_in: bool = True):
    if application_id:
        trakt.APPLICATION_ID = application_id
    else:
        trakt.core.AUTH_METHOD = trakt.core.OAUTH_AUTH
    if client_id and client_secret:
        trakt.init(username, client_id=client_id, client_secret=client_secret, store=stay_logged_in)
    else:
        trakt.init(username, store=stay_logged_in)


def get_trakt_user(username):
    try:
        return User(username)
    except Exception as e:
        error(f"Error in get_trakt_user: {e}")
    return None


class TraktConnector:
    def __init__(self, username: str, client_id: str = None, client_secret: str = None, application_id=None,
                 stay_logged_in: bool = True):
        self.username = username
        self.lists = []
        sign_in(username=username, client_id=client_id, client_secret=client_secret, application_id=application_id,
                stay_logged_in=stay_logged_in)

    def store_public_lists(self, lists_dict):
        self.lists = lists_dict

    def get_username_by_listname(self, list_name):
        # Returns first match, be warned if multiple lists with same name, different users
        for username, lists in self.lists.items():
            for list in lists:
                if list == list_name:
                    return username
        return None

    def get_list(self, list_name: str, trakt_username: str = None):
        if not trakt_username:
            trakt_username = self.get_username_by_listname(list_name=list_name)
        if trakt_username:
            trakt_user = get_trakt_user(username=trakt_username)
            return trakt_user.get_list(title=list_name)
        error("Could not locate corresponding Trakt user.")
        return None

    def get_list_items(self, list_name: str, trakt_username: str = None):
        trakt_list = self.get_list(list_name=list_name, trakt_username=trakt_username)
        return trakt_list.get_items()
