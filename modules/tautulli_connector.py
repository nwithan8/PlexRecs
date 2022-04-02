import json

import requests

from modules.logs import *


class TautulliConnector:
    def __init__(self, url, api_key, analytics):
        self.url = url
        self.api_key = api_key
        self.analytics = analytics

    def _error_and_analytics(self, error_message, function_name):
        error(error_message)
        self.analytics.event(event_category="Error", event_action=function_name, random_uuid_if_needed=True)

    def api_call_get(self, cmd, params=None):
        try:
            url = f'{self.url}/api/v2?apikey={self.api_key}{"&" + str(params) if params else ""}&cmd={cmd}'
            response = requests.get(url=url)
            if response:
                return response.json()
        except json.JSONDecodeError as e:
            self._error_and_analytics(error_message=f'Response JSON is empty: {e}',
                                      function_name='api_call_get (JSONDecodeError)')
        except ValueError as e:
            self._error_and_analytics(error_message=f'Response content is not valid JSON: {e}',
                                      function_name='api_call_get (ValueError)')
        return None

    def get_user_history(self, username, section_ids):
        try:
            user_id = None
            users = self.api_call_get(cmd='get_users')
            for user in users['response']['data']:
                if user['username'] == username:
                    user_id = user['user_id']
                    break
            if not user_id:
                self._error_and_analytics(error_message="I couldn't find that username. Please check and try again.",
                                          function_name='get_user_history (No User ID)')
                return "Error"
            watched_titles = []
            for sectionID in section_ids:
                history = self.api_call_get(cmd='get_history',
                                            params=f'section_id={sectionID}&user_id={user_id}&length=10000')
                for watched_item in history['response']['data']['data']:
                    watched_titles.append(watched_item['full_title'])
            return watched_titles
        except Exception as e:
            self._error_and_analytics(error_message=f"Error in getHistory: {e}",
                                      function_name='get_user_history (general)')
        return "Error"
