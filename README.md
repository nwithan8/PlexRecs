# PlexRecs
A Discord bot that provides movie and TV show recommendations from your Plex library

This is still a work in progress, and I hope to expand functionality in the future. Please post in Issues of any feature requests.

DISCLAIMER: This bot requires a Discord account and server, a Plex Media Server and Tautulli/PlexPy (Plex monitoring) software to function.

# Setup
HOW TO MAKE A DISCORD BOT: https://discordpy.readthedocs.io/en/rewrite/discord.html

Run the pip command at the top of the PlexRecs.py file to install the required Python packages:

	pip install discord PlexAPI imdbpie requests

# Usage
Run the script wuth the following command:
		
	python PlexRecs.py
OR
	
	python3 PlexRecs.py
(Bot works on Python 3.6.5rc1, does not work on Python 3.7+)

Once the bot is up and running, simply send a private message to the bot account, mentioning the word "recommend" or "suggest" to get started. The bot will also provide assistance for those mentioning "help","hello" or "hey" in a private message.
