import argparse
import asyncio
import sys

import modules.logs as logging
from bot import PlexRecs
from consts import (
    GOOGLE_ANALYTICS_ID,
    APP_NAME,
    DEFAULT_CONFIG_PATH,
    DEFAULT_LOG_DIR,
    CONSOLE_LOG_LEVEL,
    FILE_LOG_LEVEL,
)
from modules.analytics import GoogleAnalytics
from modules.config_parser import Config

# Parse arguments
parser = argparse.ArgumentParser(description="PlexRecs - Plex recommendations bot for Discord")

"""
Bot will use config, in order:
1. Explicit config file path provided as CLI argument, if included, or
2. Default config file path, if exists, or
3. Environmental variables
"""
parser.add_argument("-c", "--config", help="Path to config file", default=DEFAULT_CONFIG_PATH)

# Should include trailing backslash
parser.add_argument("-l", "--log", help="Log file directory", default=DEFAULT_LOG_DIR)

args = parser.parse_args()

# Set up logging
logging.init(app_name=APP_NAME, console_log_level=CONSOLE_LOG_LEVEL, log_to_file=True, log_file_dir=args.log, file_log_level=FILE_LOG_LEVEL)

# Set up configuration
config = Config(app_name=APP_NAME, config_path=f"{args.config}")

# Set up analytics
analytics = GoogleAnalytics(analytics_id=GOOGLE_ANALYTICS_ID,
                            anonymous_ip=True,
                            do_not_track=not config.extras.allow_analytics)

if __name__ == '__main__':
    logging.info("Starting PlexRecs...")
    analytics.event(event_category="Platform",
                    event_action=sys.platform)

    # Set up PlexRecs bot
    bot = PlexRecs(config=config, analytics=analytics)

    # Run bot
    asyncio.run(bot.run())
