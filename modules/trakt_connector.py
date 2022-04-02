import inspect
import json

import trakt
import trakt.core
from trakt.users import User

from modules.logs import *


def get_stored_oauth_token(filename):
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        trakt.core.OAUTH_TOKEN = data.get('OAUTH_TOKEN')
        return True
    except Exception as e:
        pass
    return False


def sign_in(username: str, client_id: str = None, client_secret: str = None, application_id=None,
            stay_logged_in: bool = True, token_path: str = trakt.core.CONFIG_PATH):
    if application_id:
        trakt.APPLICATION_ID = application_id
    else:
        trakt.core.AUTH_METHOD = trakt.core.OAUTH_AUTH
    get_stored_oauth_token(filename=token_path)
    if not trakt.core.OAUTH_TOKEN:
        if client_id and client_secret:
            trakt.init(username, client_id=client_id, client_secret=client_secret, store=stay_logged_in)
        else:
            trakt.init(username, store=stay_logged_in)


class TraktConnector:
    def __init__(self, username: str, analytics, client_id: str = None, client_secret: str = None, application_id=None,
                 stay_logged_in: bool = True):
        self.username = username
        self.lists = []
        self.analytics = analytics
        sign_in(username=username, client_id=client_id, client_secret=client_secret, application_id=application_id,
                stay_logged_in=stay_logged_in)

    def _error_and_analytics(self, error_message, function_name):
        error(error_message)
        self.analytics.event(event_category="Error", event_action=function_name, random_uuid_if_needed=True)

    def store_public_lists(self, lists_dict):
        self.lists = lists_dict

    def get_trakt_user(self, username):
        try:
            return User(username)
        except Exception as e:
            self._error_and_analytics(error_message=f"Error in get_trakt_user: {e}", function_name=inspect.currentframe().f_code.co_name)
        return None

    def get_username_by_listname(self, list_name):
        # Returns first match, be warned if multiple lists with same name, different users
        for username, lists in self.lists.items():
            for a_list in lists:
                if a_list == list_name:
                    return username
        return None

    def get_list(self, list_name: str, trakt_username: str = None):
        if not trakt_username:
            trakt_username = self.get_username_by_listname(list_name=list_name)
        if trakt_username:
            trakt_user = self.get_trakt_user(username=trakt_username)
            return trakt_user.get_list(title=list_name)
        self._error_and_analytics(error_message="Could not locate corresponding Trakt user.",
                                  function_name='get_list (trakt)')
        return None

    def get_list_items(self, list_name: str, trakt_username: str = None):
        trakt_list = self.get_list(list_name=list_name, trakt_username=trakt_username)
        print(trakt_list)
        return trakt_list.get_items()
