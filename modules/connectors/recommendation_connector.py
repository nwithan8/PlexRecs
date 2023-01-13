from modules.analytics import GoogleAnalytics
from modules.config_parser import Config
from modules.connectors.recommendation_services.trakt_connector import TraktConnector


class RecommendationConnector:

    _analytics: GoogleAnalytics

    def __init__(self, config: Config, analytics: GoogleAnalytics):
        self._analytics = analytics

"""
        self.trakt = TraktConnector(username=config.trakt.username,
                                    client_id=config.trakt.client_id,
                                    client_secret=config.trakt.client_secret,
                                    analytics=self.analytics)
        self.trakt.store_public_lists(lists_dict=config.trakt.lists)
        """
