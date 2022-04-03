import discord
from discord.ext import commands, tasks

import credentials
import modules.imdb_connector as imdb
from modules import plex_connector
from modules.analytics import GoogleAnalytics
from modules.library_database import Content
from modules.plex_connector import PlexConnector


def make_embed(plex: PlexConnector, media_item: Content, analytics: GoogleAnalytics):
    imdb_item = imdb.get_imdb_item(media_item.Title, analytics=analytics)
    embed = None
    if credentials.RETURN_PLEX_URL:
        url = f"https://app.plex.tv/desktop#!/server/{plex.server_id}/details?key=%2Flibrary%2Fmetadata%2F{media_item.RatingKey}"
        embed = discord.Embed(title=media_item.Title,
                              url=url,
                              description=f"Watch it on {credentials.PLEX_SERVER_NAME}")
        embed.add_field(name="\u200b", value=f"[Click here to watch on Plex]({url})")
    else:
        url = f"https://www.imdb.com/title/{imdb_item.imdb_id}"
        embed = discord.Embed(title=media_item.Title,
                              url=url,
                              description=f"View on IMDb")
        embed.add_field(name="\u200b", value=f"[Click here to view on IMDb]({url})")
    embed.add_field(name="Summary", value=imdb_item.plot_outline, inline=False)
    embed.add_field(name="Release Date", value=imdb_item.release_date, inline=False)
    if media_item.MediaType not in ['artist', 'album', 'track']:
        try:
            embed.set_image(url=str(imdb_item.image.url))
        except:
            pass
    return embed
