# EDIT THESE VALUES
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
    'musical artist': [3, 6],
    '4k': [4],
    'anime': [5]
}

TAUTULLI_BASE_URL = 'http://192.168.1.27:8282'
TAUTULLI_API_KEY = 'ae806d8be2b548769e79c0378a20705e'

DISCORD_BOT_TOKEN = 'NTMwNTMxNjg1OTIyNTA0NzE0.DxAv2w.hL6k3jJKVJFY5h-_D7YzRULfUAM'

# Right-click on your profile picture -> "Copy ID"
OWNER_DISCORD_ID = '233771307555094528'

BOT_PREFIX = '*'
