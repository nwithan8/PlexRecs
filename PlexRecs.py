import asyncio
import discord
from discord.ext import commands, tasks
from discord.utils import get
import credentials
from plexapi.server import PlexServer
import requests
import json
import re
from imdbpie import Imdb, ImdbFacade
import random
from progress.bar import Bar

plex = PlexServer(credentials.PLEX_URL, credentials.PLEX_TOKEN)

imdbf = ImdbFacade()
imdb = Imdb()

MOVIES = []
SHOWS = []
ARTISTS = []

owner_players = []
emoji_numbers = [u"1\u20e3", u"2\u20e3", u"3\u20e3", u"4\u20e3", u"5\u20e3"]


def request(cmd, params):
    url = '{base}/api/v2?apikey={key}&cmd={cmd}'.format(base=credentials.TAUTULLI_API_KEY,
                                                        key=credentials.TAUTULLI_API_KEY, cmd=cmd)
    if params:
        url = '{base}/api/v2?apikey={key}&{params}&cmd={cmd}'.format(base=credentials.TAUTULLI_BASE_URL,
                                                                     key=credentials.TAUTULLI_API_KEY,
                                                                     params=params, cmd=cmd)
    return json.loads(requests.get(url).text)


def cleanLibraries():
    global MOVIES, SHOWS, ARTISTS
    MOVIES.clear
    SHOWS.clear
    ARTISTS.clear


def makeLibrary(libraryNumber):
    try:
        global MOVIES, SHOWS, ARTISTS
        librarySection = plex.library.sectionByID(libraryNumber)
        json_data = request("get_library", "section_id={}".format(libraryNumber))
        count = json_data['response']['data']['count']
        if libraryNumber in credentials.MOVIE_LIBRARIES and not MOVIES:
            bar = Bar('Loading movies', max=int(count))
            for item in librarySection.all():
                MOVIES.append([item.title, item.year])
                bar.next()
            bar.finish()
            return True
        elif libraryNumber in credentials.TV_LIBRARIES and not SHOWS:
            bar = Bar('Loading TV shows', max=int(count))
            for item in librarySection.all():
                SHOWS.append([item.title, item.year])
                bar.next()
            bar.finish()
            return True
        elif libraryNumber in credentials.MOVIE_LIBRARIES and not ARTISTS:
            bar = Bar('Loading musical artists', max=int(count))
            for item in librarySection.all():
                ARTISTS.append([item.title, item.year])
                bar.next()
            bar.finish()
            return True
        else:
            return False
    except Exception as e:
        print('Error grabbing libraries: {}'.format(e))
        return False


def getPoster(embed, title):
    try:
        embed.set_image(url=str(imdbf.get_title(imdb.search_for_title(title)[0]['imdb_id']).image.url))
        return embed
    except Exception as e:
        print("Error getting poster: {}".format(e))
        return embed


def makeEmbed(mediaItem):
    embed = discord.Embed(title=mediaItem.title,
                          url='{base}/web/index.html#!/server/{id}/details?key=%2Flibrary%2Fmetadata%2F{ratingKey}'.format(
                              base=credentials.PLEX_URL, id=credentials.PLEX_SERVER_ID, ratingKey=mediaItem.ratingKey),
                          description="Watch it on {}".format(credentials.PLEX_SERVER_NAME))
    embed = getPoster(embed, mediaItem.title)
    return embed


def getHistory(username, sectionIDs):
    user_id = ""
    users = request('get_users', None)
    for user in users['response']['data']:
        if user['username'] == username:
            user_id = user['user_id']
            break
    if not user_id:
        print("I couldn't find that username. Please check and try again.")
        return False
    watched_titles = []
    for sectionID in sectionIDs:
        history = request('get_history', 'section_id={}&user_id={}&length=10000'.format(str(sectionID), user_id))
        for watched_item in history['response']['data']['data']:
            watched_titles.append(watched_item['full_title'])
    return watched_titles


def pickUnwatched(history, mediaList):
    """
    Keep picking until something is unwatched
    :param history:
    :param mediaList: Movies list, Shows list or Artists list
    :return:
    """
    if not history:
        return False
    choice = random.choice(mediaList)
    if choice.title in history:
        return pickUnwatched(history, mediaList)
    return choice


def pickRandom(aList):
    return random.choice(aList)


def findRec(username, mediaType, unwatched=False):
    """

    :param username:
    :param unwatched:
    :param mediaType: 'movie', 'show' or 'artist'
    :return:
    """
    try:
        if unwatched:
            if mediaType == 'movie':
                return pickUnwatched(history=getHistory(username, credentials.MOVIE_LIBRARIES), mediaList=MOVIES)
            elif mediaType == 'show':
                return pickUnwatched(history=getHistory(username, credentials.TV_LIBRARIES), mediaList=SHOWS)
            elif mediaType == 'artist':
                return pickUnwatched(history=getHistory(username, credentials.MUSIC_LIBRARIES), mediaList=ARTISTS)
        else:
            if mediaType == 'movie':
                return pickRandom(MOVIES)
            elif mediaType == 'show':
                return pickRandom(SHOWS)
            elif mediaType == 'artist':
                return pickRandom(ARTISTS)
    except Exception as e:
        print("Error in findRec: {}".format(e))
        return False


def makeRecommendation(mediaType, unwatched, PlexUsername):
    if unwatched:
        if not PlexUsername:
            return "Please include a Plex username"
        recommendation = findRec(PlexUsername, mediaType, True)
        if not recommendation:
            return "I couldn't find that Plex username"
        embed = makeEmbed(recommendation)
        return "How about {}?".format(recommendation.title), embed, recommendation


def getPlayers(mediaType):
    global owner_players
    owner_players = []
    players = plex.clients()
    if not players:
        return False
    num = 0
    players_list = ""
    for player in players[:5]:
        num = num + 1
        players_list = '{}\n{}:{}'.format(players_list, num, player.title)
        owner_players.append(player)
    return '{}\nReact with which player you want to start this {} on.'.format(players_list, mediaType), num


def playMedia(playerNumber, mediaItem):
    owner_players[playerNumber].goToMedia(mediaItem)


class PlexRecs(commands.Cogs):

    @tasks.loop(minutes=60.0)  # update library every hour
    async def makeLibraries(self):
        cleanLibraries()
        libraryNumbers = credentials.MOVIE_LIBRARIES + list(
            set(credentials.TV_LIBRARIES) - set(credentials.MOVIE_LIBRARIES))
        libraryNumbers = libraryNumbers + list(set(credentials.MUSIC_LIBRARIES) - set(libraryNumbers))
        for libraryNumber in libraryNumbers:
            makeLibrary(libraryNumber)

    @commands.group(aliases=['recommend', 'suggest', 'rec', 'sugg'], pass_context=True)
    async def plex_rec(self, ctx: commands.Context, mediaType: str):
        """
        Movie, show or artist recommendation from Plex

        Say 'movie', 'show' or 'artist'
        Use 'rec <mediaType> new <PlexUsername>' for an unwatched recommendation.
        """
        if ctx.invoked_subcommand is None:
            if mediaType.lower() not in ['movie', 'show', 'artist']:
                await ctx.send("Please try again, indicating either 'movie', 'show', or 'artist'")
            else:
                await ctx.send("Looking for a {}...".format(mediaType))
                async with ctx.typing():
                    response, embed, mediaItem = makeRecommendation(mediaType, False, None)
                    if embed is not None:
                        await ctx.send(response, embed=embed)
                    else:
                        await ctx.send(response)
                    if ctx.message.author.id == credentials.OWNER_DISCORD_ID:
                        askAboutPlayer = True
                        while askAboutPlayer:
                            try:
                                def check(react, reactUser, numPlayers):
                                    return str(react.emoji) in emoji_numbers[
                                                               :numberOfPlayers] and reactUser.id == credentials.OWNER_DISCORD_ID

                                response, numberOfPlayers = getPlayers()
                                playerQuestion = await ctx.send(response)
                                for i in range(0, numberOfPlayers - 1):
                                    await playerQuestion.add_reaction(emoji_numbers[i])
                                reaction, user = await self.bot.wait_fo('reaction_add', timeout=60.0, check=check)
                                if reaction:
                                    playerNumber = emoji_numbers.index(str(reaction.emoji))
                                    playMedia(playerNumber, mediaItem)
                            except asyncio.TimeoutError:
                                await playerQuestion.delete()
                                askAboutPlayer = False

    @plex_rec.error
    async def plex_rec_error(self, ctx, error):
        print(error)
        await ctx.send("Sorry, something went wrong while looking for a recommendation.")

    @plex_rec.command(name="new", aliases=['unwatched', 'unseen', 'unlistened'])
    async def plex_rec_new(self, ctx: commands.Context, PlexUsername: str):
        """
        Get a new movie, show or artist recommendation
        Include your Plex username
        """
        mediaType = None
        if 'movie' in ctx.message.content.lower():
            mediaType = 'movie'
        elif 'show' in ctx.message.content.lower():
            mediaType = 'show'
        elif 'artist' in ctx.message.content.lower():
            mediaType = 'artist'
        else:
            pass
        if not mediaType:
            await ctx.send("Please try again, indicating either 'movie', 'show', or 'artist'")
        else:
            await ctx.send("Looking for a new {}...".format(mediaType))
            async with ctx.typing():
                response, embed, mediaItem = makeRecommendation(mediaType, True, PlexUsername)
                if embed is not None:
                    await ctx.send(response, embed=embed)
                else:
                    await ctx.send(response)
                if ctx.message.author.id == credentials.OWNER_DISCORD_ID:
                    askAboutPlayer = True
                    while askAboutPlayer:
                        try:
                            def check(react, reactUser, numPlayers):
                                return str(react.emoji) in emoji_numbers[
                                                           :numberOfPlayers] and reactUser.id == credentials.OWNER_DISCORD_ID

                            response, numberOfPlayers = getPlayers()
                            playerQuestion = await ctx.send(response)
                            for i in range(0, numberOfPlayers - 1):
                                await playerQuestion.add_reaction(emoji_numbers[i])
                            reaction, user = await self.bot.wait_fo('reaction_add', timeout=60.0, check=check)
                            if reaction:
                                playerNumber = emoji_numbers.index(str(reaction.emoji))
                                playMedia(playerNumber, mediaItem)
                        except asyncio.TimeoutError:
                            await playerQuestion.delete()
                            askAboutPlayer = False

    @plex_rec_new.error
    async def plex_rec_new_error(self, ctx, error):
        print(error)
        await ctx.send("Sorry, something went wrong while looking for a new recommendation.")

    def __init__(self, bot):
        self.bot = bot
        print("Updating Plex libraries...")
        self.makeLibraries.start()
