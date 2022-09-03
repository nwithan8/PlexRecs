# PlexRecs
A Discord bot that provides movie and TV show recommendations from your Plex library

DISCLAIMER: This bot requires a Discord account and server, a Plex Media Server and Tautulli/PlexPy (Plex monitoring) software to function. **Requires Python 3.6+**

# Setup
1. Make a Discord Bot (HOW TO MAKE A DISCORD BOT: https://discordpy.readthedocs.io/en/rewrite/discord.html). Bot will need read/write text channel permissions, including links, attachments and emojis, and message management. 
2. Clone this repo with ``git clone https://github.com/nwithan8/PlexRecs.git``
3. Navigate to PlexRecs directory with ``cd PlexRecs``
4. Install dependencies with ``pip3 install -r requirements.txt``
5. Rename the ``config.yaml.example`` file to ``config.yaml`` and fill out the credentials
6. Run the bot with ``python3 run.py``

# Usage

Once the bot is up and running, trigger it by typing "[PREFIX] recommend [CATEGORY]" to get a randomly selected movie/show/artist recommendation.

To only get recommended something you have not already watched/listened to, type "[PREFIX] recommend [CATEGORY] new [Your Plex Username]".

# Features
In addition to a recommendation, the owner of the Plex Server (whoever has the OWNER_DISCORD_ID) will be offered up to five available players that they can have the recommendation automatically play on.

Due to security limitations in the Plex API, this option is only available for the user currently logged into Plex (in this case, the Plex server administrator).

# Analytics
PlexRecs uses Google Analytics to collect statistics about usage to help me identity common errors, as well as what features are used most often to help guide and focus future development. **This data is limited, anonymous, and never sold or redistributed.**

**When and what data is collected?**
- Whenever the bot comes online
	- What operating system the bot is running on (Windows, Linux, MacOS, etc.)
- Whenever an error is logged
	- What Python function the error occurred in.
- Whenever a recommendation is successfully made
	- What type of recommendation (regular, new, IMDb rating, from Trakt list) was made.
	- NO DETAILS about the recommended item are transmitted
	
**What data is NOT collected:**
- Any identifying information about the user
- Any identifying information about the computer/machine (a random ID is generated on each analytics call, IP addresses are anonymized)
- Settings for Discord, Plex, Tautulli or Trakt, including passwords, API tokens, URLs, etc.
- Anything typed in Discord.

# Contact
Please leave a pull request if you would like to contribute.

Follow me on Twitter: [@nwithan8](https://twitter.com/nwithan8)

Also feel free to check out my other projects here on [GitHub](https://github.com/nwithan8) or join the #developer channel in my Discord server below.

<div align="center">
	<p>
		<a href="https://discord.gg/ygRDVE9"><img src="https://discordapp.com/api/guilds/472537215457689601/widget.png?style=banner2" alt="" /></a>
	</p>
</div>

