from modules.analytics import GoogleAnalytics
from modules.config_parser import Config
from modules.connectors.discord_connector import DiscordConnector
from modules.connectors.plex_connector import PlexConnector
from modules.connectors.recommendation_connector import RecommendationConnector

class PlexRecs:

    _analytics: GoogleAnalytics
    _discord_connector: DiscordConnector
    _plex_connector: PlexConnector
    _recommendation_connector: RecommendationConnector

    def __init__(self, config: Config, analytics: GoogleAnalytics):
        self._analytics = analytics

        # plex_config = config.plex
        # self._plex_connector = PlexConnector(config=plex_config, analytics=analytics)

        recommendation_config = config.recommendation_services
        self._recommendation_connector = RecommendationConnector(config=recommendation_config, analytics=analytics)

        discord_config = config.discord
        self._discord_connector = DiscordConnector(config=discord_config, analytics=analytics)

    def _fetch_recommendation(self, **kwargs):
        return "Answer from callback"

    async def run(self):
        # self.plex_connector.initialize_libraries()
        await self._discord_connector.load_recommendation_commands(recommendation_callback=self._fetch_recommendation)
        await self._discord_connector.connect() # Needs to be the last thing started


