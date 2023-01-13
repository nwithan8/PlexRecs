import os
from typing import List, Dict

import confuse


def _extract_bool(value):
    if isinstance(value, bool):
        return value
    if value.lower() in ["true", "yes", "1", "t"]:
        return True
    elif value.lower() in ["false", "no", "0", "f"]:
        return False
    else:
        raise ValueError("Not a boolean: {}".format(value))


class ConfigSection:
    def __init__(self, section_key: str, data, parent_key: str = None, pull_from_env: bool = True):
        self.section_key = section_key
        self.data = data
        self.pull_from_env = pull_from_env
        try:
            self.data = data[self.section_key]
        except confuse.NotFoundError:
            pass
        self._parent_key = parent_key

    @property
    def full_key(self):
        if self._parent_key is None:
            return self.section_key
        return f"{self._parent_key}_{self.section_key}".upper()

    def _get_value(self, key: str, default=None, env_name_override: str = None):
        if self.pull_from_env:
            env_name = env_name_override or self.full_key
            return os.getenv(env_name, default)
        try:
            return self.data[key].get()
        except confuse.NotFoundError:
            return default

    def _get_subsection(self, key: str, default=None):
        try:
            return ConfigSection(section_key=key, parent_key=self.full_key, data=self.data,
                                 pull_from_env=self.pull_from_env)
        except confuse.NotFoundError:
            return default


class PlexConfig(ConfigSection):
    def __init__(self, data, pull_from_env: bool = True):
        super().__init__(section_key="Plex", data=data, pull_from_env=pull_from_env)

    @property
    def url(self) -> str:
        return self._get_value(key="URL", env_name_override="PR_PLEX_URL")

    @property
    def token(self) -> str:
        return self._get_value(key="Token", env_name_override="PR_PLEX_TOKEN")

    @property
    def server_name(self) -> str:
        return self._get_value(key="ServerName", env_name_override="PR_PLEX_SERVER_NAME")

    @property
    def use_plex_link(self) -> bool:
        return self._get_value(key="UsePlexLink", default=True, env_name_override="PR_USE_PLEX_LINK")

    @property
    def library_update_interval_minutes(self) -> int:
        return self._get_value(key="LibraryUpdateIntervalMinutes", default=True,
                               env_name_override="PR_LIBRARY_UPDATE_INTERVAL_MINUTES")

    @property
    def _libraries_section(self):
        return self._get_subsection(key="Libraries")

    @property
    def _movies_libraries(self) -> List[str]:
        data = self._libraries_section._get_value(key="Movies", default=[],
                                                  env_name_override="PR_PLEX_MOVIES_LIBRARIES")
        if isinstance(data, str):
            return data.split(",")  # Dealing with a comma separated list in an environment variable
        return data

    @property
    def _shows_libraries(self) -> List[str]:
        data = self._libraries_section._get_value(key="Shows", default=[],
                                                  env_name_override="PR_PLEX_SHOWS_LIBRARIES")
        if isinstance(data, str):
            return data.split(",")  # Dealing with a comma separated list in an environment variable
        return data

    @property
    def _music_libraries(self) -> List[str]:
        data = self._libraries_section._get_value(key="Music", default=[],
                                                  env_name_override="PR_PLEX_MUSIC_LIBRARIES")
        if isinstance(data, str):
            return data.split(",")  # Dealing with a comma separated list in an environment variable
        return data

    @property
    def _4K_libraries(self) -> List[str]:
        data = self._libraries_section._get_value(key="4K", default=[],
                                                  env_name_override="PR_PLEX_4K_LIBRARIES")
        if isinstance(data, str):
            return data.split(",")  # Dealing with a comma separated list in an environment variable
        return data

    @property
    def _anime_libraries(self) -> List[str]:
        data = self._libraries_section._get_value(key="Anime", default=[],
                                                  env_name_override="PR_PLEX_ANIME_LIBRARIES")
        if isinstance(data, str):
            return data.split(",")  # Dealing with a comma separated list in an environment variable
        return data

    @property
    def libraries(self):
        return {
            "movie": self._movies_libraries,
            "show": self._shows_libraries,
            "music": self._music_libraries,
            "4k": self._4K_libraries,
            "anime": self._anime_libraries,
        }


class TautulliConfig(ConfigSection):
    def __init__(self, data, pull_from_env: bool = True):
        super().__init__(section_key="Tautulli", data=data, pull_from_env=pull_from_env)

    @property
    def api_key(self) -> str:
        return self._get_value(key="ApiKey", env_name_override="PR_TAUTULLI_KEY")

    @property
    def url(self) -> str:
        return self._get_value(key="URL", env_name_override="PR_TAUTULLI_URL")


class DiscordConfig(ConfigSection):
    def __init__(self, data, pull_from_env: bool = True):
        super().__init__(section_key="Discord", data=data, pull_from_env=pull_from_env)

    @property
    def bot_token(self) -> str:
        return self._get_value(key="BotToken", env_name_override="PR_DISCORD_BOT_TOKEN")

    @property
    def bot_prefix(self) -> str:
        return self._get_value(key="BotPrefix", env_name_override="PR_DISCORD_BOT_PREFIX")

    @property
    def owner_id(self) -> str:
        return self._get_value(key="OwnerID", env_name_override="PR_DISCORD_OWNER_ID")

class TraktConfig(ConfigSection):
    def __init__(self, data, pull_from_env: bool = True):
        super().__init__(section_key="Trakt", data=data, pull_from_env=pull_from_env)

    @property
    def username(self) -> str:
        return self._get_value(key="Username", env_name_override="PR_TRAKT_USERNAME")

    @property
    def client_id(self) -> str:
        return self._get_value(key="ClientID", env_name_override="PR_TRAKT_CLIENT_ID")

    @property
    def client_secret(self) -> str:
        return self._get_value(key="ClientSecret", env_name_override="PR_TRAKT_CLIENT_SECRET")

    @property
    def lists(self) -> Dict:
        data = self._get_value(key="Lists", default=[], env_name_override="PR_TRAKT_LISTS")
        if isinstance(data, str):
            """
            For environment variables, we need to convert one string to a list of strings first
            Example: username1/listname1,username1/listname2,username3/listname3
            """
            data = data.split(",")
        lists = {}
        for entry in data:
            username, list_name = entry.split("/")
            if username not in lists:
                lists[username] = []
            lists[username].append(list_name)
        """
        Example:
        {
            "username1": ["listname1", "listname2"],
            "username2": ["listname3"]
        }
        """
        return lists

class RecommendationServicesConfig(ConfigSection):
    def __init__(self, data, pull_from_env: bool = True):
        super().__init__(section_key="RecServices", data=data, pull_from_env=pull_from_env)

    @property
    def trakt(self) -> TraktConfig:
        return self._get_subsection(key="Trakt")


class ExtrasConfig(ConfigSection):
    def __init__(self, data, pull_from_env: bool = True):
        super().__init__(section_key="Extras", data=data, pull_from_env=pull_from_env)

    @property
    def allow_analytics(self) -> bool:
        value = self._get_value(key="Analytics", default=True,
                                env_name_override="PR_ALLOW_ANALYTICS")
        return _extract_bool(value)

    @property
    def suppress_logs(self) -> bool:
        value = self._get_value(key="SuppressLogs", default=False,
                                env_name_override="PR_SUPPRESS_LOGS")
        return _extract_bool(value)


class Config:
    def __init__(self, app_name: str, config_path: str, fallback_to_env: bool = True):
        self.config = confuse.Configuration(app_name)
        self.pull_from_env = False
        # noinspection PyBroadException
        try:
            self.config.set_file(filename=config_path)
        except Exception:  # pylint: disable=broad-except # not sure what confuse will throw
            if not fallback_to_env:
                raise FileNotFoundError(f"Config file not found: {config_path}")
            self.pull_from_env = True

        self.plex = PlexConfig(data=self.config, pull_from_env=self.pull_from_env)
        self.tautulli = TautulliConfig(self.config, self.pull_from_env)
        self.discord = DiscordConfig(self.config, self.pull_from_env)
        self.recommendation_services = RecommendationServicesConfig(self.config, self.pull_from_env)
        self.extras = ExtrasConfig(self.config, self.pull_from_env)
        try:
            self.log_level = self.config['logLevel'].get() or "INFO"
        except confuse.NotFoundError:
            self.log_level = "WARN"  # will only be WARN when pulling config from env (i.e. Docker)
