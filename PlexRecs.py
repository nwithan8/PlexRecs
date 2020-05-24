import asyncio
import discord
from discord.ext import commands, tasks
import credentials
from plexapi.server import PlexServer
import requests
import json
from imdbpie import Imdb, ImdbFacade
import random
from progress.bar import Bar

plex = PlexServer(credentials.PLEX_URL, credentials.PLEX_TOKEN)

imdbf = ImdbFacade()
imdb = Imdb()

libraries = {}
for name, numbers in credentials.LIBRARIES.items():
    libraries[name] = [numbers, []]

owner_players = []
emoji_numbers = [u"1\u20e3", u"2\u20e3", u"3\u20e3", u"4\u20e3", u"5\u20e3"]


def request(cmd, params):
    url = '{base}/api/v2?apikey={key}&cmd={cmd}'.format(base=credentials.TAUTULLI_BASE_URL,
                                                        key=credentials.TAUTULLI_API_KEY, cmd=cmd)
    if params:
        url = '{base}/api/v2?apikey={key}&{params}&cmd={cmd}'.format(base=credentials.TAUTULLI_BASE_URL,
                                                                     key=credentials.TAUTULLI_API_KEY,
                                                                     params=params, cmd=cmd)
    return json.loads(requests.get(url).text)


def cleanLibraries():
    global libraries
    for groupName, items in libraries.items():
        items[1].clear


class SmallMediaItem:
    def __init__(self, title, year, ratingKey, librarySectionID):
        self.title = title
        self.year = year
        self.ratingKey = ratingKey
        self.librarySectionID = librarySectionID


def makeLibrary(libraryName):
    try:
        global libraries
        if not libraries[libraryName][1]:
            for libraryNumber in libraries[libraryName][0]:
                json_data = request("get_library", "section_id={}".format(libraryNumber))
                count = json_data['response']['data']['count']
                bar = Bar('Loading {} (Library section {})'.format(libraryName, libraryNumber), max=int(count))
                librarySection = plex.library.sectionByID(str(libraryNumber))
                for item in librarySection.all():
                    libraries[libraryName][1].append(SmallMediaItem(item.title, (None if librarySection.type == 'artist' else item.year), item.ratingKey, item.librarySectionID))
                    bar.next()
                bar.finish()
            return True
        return False
    except Exception as e:
        print('Error in makeLibrary: {}'.format(e))
        return False


def getPoster(embed, title):
    try:
        embed.set_image(url=str(imdbf.get_title(imdb.search_for_title(title)[0]['imdb_id']).image.url))
        return embed
    except Exception as e:
        print("Error in getPoster: {}".format(e))
        return embed


def makeEmbed(mediaItem):
    embed = discord.Embed(title=mediaItem.title,
                          url='{base}/web/index.html#!/server/{id}/details?key=%2Flibrary%2Fmetadata%2F{ratingKey}'.format(
                              base=credentials.PLEX_URL, id=credentials.PLEX_SERVER_ID, ratingKey=mediaItem.ratingKey,
                              description="Watch it on {}".format(credentials.PLEX_SERVER_NAME)))
    if mediaItem.type not in ['artist', 'album', 'track']:
        embed = getPoster(embed, mediaItem.title)
    return embed


def getHistory(username, sectionIDs):
    try:
        user_id = None
        users = request('get_users', None)
        for user in users['response']['data']:
            if user['username'] == username:
                user_id = user['user_id']
                break
        if not user_id:
            print("I couldn't find that username. Please check and try again.")
            return "Error"
        watched_titles = []
        for sectionID in sectionIDs:
            history = request('get_history', 'section_id={}&user_id={}&length=10000'.format(str(sectionID), user_id))
            for watched_item in history['response']['data']['data']:
                watched_titles.append(watched_item['full_title'])
        return watched_titles
    except Exception as e:
        print("Error in getHistory: {}".format(e))
        return "Error"


def pickUnwatched(history, mediaList):
    """
    Keep picking until something is unwatched
    :param history:
    :param mediaList: Movies list, Shows list or Artists list
    :return: SmallMediaItem object
    """
    if history == "Error":
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
            return pickUnwatched(history=getHistory(username, libraries[mediaType][0]), mediaList=libraries[mediaType][1])
        else:
            return pickRandom(libraries[mediaType][1])
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
    else:
        recommendation = findRec(None, mediaType, False)
    embed = makeEmbed(recommendation)
    return "How about {}?".format(recommendation.title), embed, recommendation


def getPlayers(mediaType):
    global owner_players
    owner_players = []
    players = plex.clients()
    if not players:
        return False, 0
    num = 0
    players_list = ""
    for player in players[:5]:
        num = num + 1
        players_list = '{}\n{}:{}'.format(players_list, num, player.title)
        owner_players.append(player)
    return '{}\nReact with which player you want to start this {} on.'.format(players_list, mediaType), num


def getFullMediaItem(mediaItem):
    librarySection = plex.library.sectionByID(mediaItem.librarySectionID)
    for item in librarySection.search(title=mediaItem.title, year=[mediaItem.year]):
        if item.ratingKey == mediaItem.ratingKey:
            return item
    return None


def playMedia(playerNumber, mediaItem):
    owner_players[playerNumber].goToMedia(mediaItem)


class PlexRecs(commands.Cog):

    @tasks.loop(minutes=60.0)  # update library every hour
    async def makeLibraries(self):
        cleanLibraries()
        for groupName in libraries.keys():
            makeLibrary(groupName)

    @commands.group(aliases=['recommend', 'suggest', 'rec', 'sugg'], pass_context=True)
    async def plex_rec(self, ctx: commands.Context, mediaType: str):
        """
        Movie, show or artist recommendation from Plex

        Say 'movie', 'show' or 'artist'
        Use 'rec <mediaType> new <PlexUsername>' for an unwatched recommendation.
        """
        if ctx.invoked_subcommand is None:
            if mediaType.lower() not in libraries.keys():
                acceptedTypes = "', '".join(libraries.keys())
                await ctx.send("Please try again, indicating '{}'".format(acceptedTypes))
            else:
                holdMessage = await ctx.send(
                    "Looking for a{} {}...".format("n" if (mediaType[0] in ['a', 'e', 'i', 'o', 'u']) else "",
                                                   mediaType))
                async with ctx.typing():
                    response, embed, mediaItem = makeRecommendation(mediaType, False, None)
                await holdMessage.delete()
                if embed is not None:
                    await ctx.send(response, embed=embed)
                else:
                    await ctx.send(response)
                if str(ctx.message.author.id) == str(credentials.OWNER_DISCORD_ID):
                    response, numberOfPlayers = getPlayers(mediaType)
                    if response:
                        askAboutPlayer = True
                        while askAboutPlayer:
                            try:
                                def check(react, reactUser, numPlayers):
                                    return str(react.emoji) in emoji_numbers[
                                                               :numberOfPlayers] and reactUser.id == credentials.OWNER_DISCORD_ID

                                playerQuestion = await ctx.send(response)
                                for i in range(0, numberOfPlayers - 1):
                                    await playerQuestion.add_reaction(emoji_numbers[i])
                                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
                                if reaction:
                                    playerNumber = emoji_numbers.index(str(reaction.emoji))
                                    mediaItem = getFullMediaItem(mediaItem)
                                    if mediaItem:
                                        playMedia(playerNumber, mediaItem)
                                    else:
                                        await ctx.send(
                                            "Sorry, something went wrong while loading that {}.".format(mediaType))
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
        for group in libraries.keys():
            if group in ctx.message.content:
                mediaType = group
                break
        if not mediaType:
            acceptedTypes = "', '".join(libraries.keys())
            await ctx.send("Please try again, indicating '{}'".format(acceptedTypes))
        else:
            holdMessage = await ctx.send("Looking for a new {}...".format(mediaType))
            async with ctx.typing():
                response, embed, mediaItem = makeRecommendation(mediaType, True, PlexUsername)
            await holdMessage.delete()
            if embed is not None:
                await ctx.send(response, embed=embed)
            else:
                await ctx.send(response)
            if str(ctx.message.author.id) == str(credentials.OWNER_DISCORD_ID):
                response, numberOfPlayers = getPlayers(mediaType)
                if response:
                    askAboutPlayer = True
                    while askAboutPlayer:
                        try:
                            def check(react, reactUser, numPlayers):
                                return str(react.emoji) in emoji_numbers[
                                                           :numberOfPlayers] and reactUser.id == credentials.OWNER_DISCORD_ID

                            playerQuestion = await ctx.send(response)
                            for i in range(0, numberOfPlayers - 1):
                                await playerQuestion.add_reaction(emoji_numbers[i])
                            reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
                            if reaction:
                                playerNumber = emoji_numbers.index(str(reaction.emoji))
                                mediaItem = getFullMediaItem(mediaItem)
                                if mediaItem:
                                    playMedia(playerNumber, mediaItem)
                                else:
                                    await ctx.send(
                                        "Sorry, something went wrong while loading that {}.".format(mediaType))
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
