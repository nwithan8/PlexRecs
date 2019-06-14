# PlexRecs
A Discord bot that provides movie and TV show recommendations from your Plex library

This is still a work in progress, and I hope to expand functionality in the future. Please post in Issues of any feature requests.

DISCLAIMER: This bot requires a Discord account and server, a Plex Media Server and Tautulli/PlexPy (Plex monitoring) software to function.

# Setup
HOW TO MAKE A DISCORD BOT: https://discordpy.readthedocs.io/en/rewrite/discord.html

Run the pip command at the top of the PlexRecs.py file to install the required Python packages:

	pip3 install discord PlexAPI imdbpie requests

# Usage
Run the script with the following command:
	
	python3 PlexRecs.py

Once the bot is up and running, simply send a private message to the bot account, mentioning the word "recommend" or "suggest" to get started. The bot will also provide assistance for those mentioning "help","hello" or "hey" in a private message.

# Features
Users can also select which active Plex player to beam the content to, in case you want to watch it on another platform. This feature is exclusive to the bot owner; since the script uses the owner's Plex account specifically for retrieving libraries and playing media, this can only be done on devices registered to the user's personal account. As it stands right now, there is no foreseeable way to circumvent this. (That's probably for the best. Don't want someone being able to remotely control another person's Plex).

TO COME:
-Music library option
-Multiple library support
-Simplier "Try Again"
