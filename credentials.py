PLEX_URL = ""
PLEX_TOKEN = ""
PLEX_SERVER_NAME = ""

# http://[PMS_IP_Address]:32400/library/sections?X-Plex-Token=YourTokenGoesHere
# Use the above link to find the number for each library: composite="/library/sections/NUMBER/composite/..."


"""
Fill out this structure, grouping libraries into whatever sub-categories you would like.
All group names must be all lowercase and a single word
NOTE: The sub-category name will have to be used as a keyword in the command.
For example, to recommend something from an 'anime' group, users will have to use the word 'anime' in their command.
"""
LIBRARIES = {
    'movie': [1],
    'show': [2],
    'music': [3, 6],
    '4k': [4],
}

TAUTULLI_BASE_URL = ""
TAUTULLI_API_KEY = ""

DISCORD_BOT_TOKEN = ""

RETURN_PLEX_URL = True  # True - recommendation has link to Plex. False - recommendation has link to IMDb page.

# Right-click on your profile picture -> "Copy ID"
OWNER_DISCORD_ID = ""

BOT_PREFIX = '?'

SUPPRESS_LOGS = False  # True - only show errors. False - show detailed info

# Make a Trakt application: https://trakt.tv/oauth/applications
TRAKT_USERNAME = ""
TRAKT_CLIENT_ID = ""
TRAKT_CLIENT_SECRET = ""

# Indicate the Trakt username and the list name for each public list you want to possibly use.
# NOTE: Only public lists work
TRAKT_LISTS = {
    'username': ['list_name_1', 'list_name_2'],
    'username2': ['list_name_3'],
    'username3': ['list_name_4']
}

"""
PlexRecs uses Google Analytics to collect statistics about usage to help me identity common errors, as well as what 
features are used most often to help guide and focus future development.
This data is limited, anonymous, and never sold or redistributed.

When and what data is collected?
    - Whenever the bot comes online
        - What operating system the bot is running on (Windows, Linux, MacOS, etc.)
    - Whenever an error is logged
        - What Python function the error occurred in.
    - Whenever a recommendation is successfully made
        - What type of recommendation (regular, new, IMDb rating, from Trakt list) was made.
        - NO DETAILS about the recommended item are transmitted

What data is NOT collected:
- Any identifying information about the user
- Any identifying information about the computer/machine (a random ID is generated on each analytics call, IP addresses are anonymized)
- Settings for Discord, Plex, Tautulli or Trakt, including passwords, API tokens, URLs, etc.
- Anything typed in Discord.

If you would like to opt-out of analytics, change True below to False
"""
ALLOW_ANALYTICS = True
