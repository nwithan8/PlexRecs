import requests
import json
from modules.logs import *


class TautulliConnector:
    def __init__(self, url, api_key):
        self.url = url
        self.api_key = api_key

    def api_call_get(self, cmd, params=None):
        try:
            url = f'{self.url}/api/v2?apikey={self.api_key}{"&" + str(params) if params else ""}&cmd={cmd}'
            response = requests.get(url=url)
            if response:
                return response.json()
        except json.JSONDecodeError as e:
            error(f'Response JSON is empty: {e}')
        except ValueError as e:
            error(f'Response content is not valid JSON: {e}')
        return None

    def get_user_history(self, username, sectionIDs):
        try:
            user_id = None
            users = self.api_call_get(cmd='get_users')
            for user in users['response']['data']:
                if user['username'] == username:
                    user_id = user['user_id']
                    break
            if not user_id:
                error("I couldn't find that username. Please check and try again.")
                return "Error"
            watched_titles = []
            for sectionID in sectionIDs:
                history = self.api_call_get(cmd='get_history', params=f'section_id={sectionID}&user_id={user_id}&length=10000')
                for watched_item in history['response']['data']['data']:
                    watched_titles.append(watched_item['full_title'])
            return watched_titles
        except Exception as e:
            error(f"Error in getHistory: {e}")
        return "Error"
