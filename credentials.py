# EDIT THESE VALUES
import os

PLEX_URL = ''
PLEX_TOKEN = ''
PLEX_SERVER_ID = ''  # after "/server/" in browser UI URL
PLEX_SERVER_NAME = ''

# http://[PMS_IP_Address]:32400/library/sections?X-Plex-Token=YourTokenGoesHere
# Use the above link to find the number for each library: composite="/library/sections/NUMBER/composite/..."
#
# Fill out this structure, grouping libraries into whatever sub-categories you would like. All group names must be
# all lowercase.
# NOTE: The sub-category name will have to be used as a keyword in the command.
# For example, to recommend something from an 'anime' group, users will have to use the word 'anime' in their command.
LIBRARIES = {
    'movie': [1],
    'show': [2],
    'music': [3, 6],
    '4k': [4],
    'anime': [5]
}

TAUTULLI_BASE_URL = ''
TAUTULLI_API_KEY = ''

DISCORD_BOT_TOKEN = ''

# Right-click on your profile picture -> "Copy ID"
OWNER_DISCORD_ID = ''

BOT_PREFIX = '?'
