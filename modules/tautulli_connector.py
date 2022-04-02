from typing import List

import tautulli

from modules.logs import *


class TautulliConnector:
    def __init__(self, url, api_key, analytics):
        self.api = tautulli.ObjectAPI(base_url=url, api_key=api_key)
        self.analytics = analytics

    def _error_and_analytics(self, error_message, function_name):
        error(error_message)
        self.analytics.event(event_category="Error", event_action=function_name, random_uuid_if_needed=True)

    def get_library(self, library_number: int):
        return self.api.get_library(section_id=str(library_number))

    def get_user_history(self, username: str, section_ids: List[int]):
        user = None
        users = self.api.users
        for _user in users:
            if user.username == username:
                user = _user
                break
        if not user:
            self._error_and_analytics(error_message="I couldn't find that username. Please check and try again.",
                                      function_name='get_user_history (No Username Match)')
            return "Error"
        watched_titles = []
        for section_id in section_ids:
            section_history = self.api.get_history(user_id=user.user_id, section_id=section_id)
            for item in section_history.data:
                watched_titles.append(item.full_title)
        return watched_titles
