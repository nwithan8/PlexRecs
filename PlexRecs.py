import asyncio
import discord
from discord.ext import commands, tasks
import credentials
from plexapi.server import PlexServer
from plexapi import exceptions as plex_exceptions
import requests
import json
from imdbpie import ImdbFacade
import random
from progress.bar import Bar
import logging
from typing import Union

logging.basicConfig(format='%(levelname)s:%(message)s',
                    level=(logging.ERROR if credentials.SUPPRESS_LOGS else logging.INFO))

plex = PlexServer(credentials.PLEX_URL, credentials.PLEX_TOKEN)
logging.info("Connected to Plex.")

imdb = ImdbFacade()

libraries = {}
for name, numbers in credentials.LIBRARIES.items():
    libraries[name] = [numbers, []]
logging.info(f"Libraries: {libraries}")

owner_players = []
emoji_numbers = [u"1\u20e3", u"2\u20e3", u"3\u20e3", u"4\u20e3", u"5\u20e3"]


def get_imdb_item(title):
    try:
        search_results = imdb.search_for_title(title)
        if search_results:
            return imdb.get_title(search_results[0].imdb_id)
    except Exception as e:
        logging.error(f"Could not get IMDb item: {e}")
    return None


def request(cmd, params):
    try:
        url = f'{credentials.TAUTULLI_BASE_URL}/api/v2?apikey={credentials.TAUTULLI_API_KEY}{"&" + str(params) if params else ""}&cmd={cmd}'
        response = requests.get(url=url)
        if response:
            return response.json()
    except json.JSONDecodeError as e:
        logging.error(f'Response JSON is empty: {e}')
    except ValueError as e:
        logging.error(f'Response content is not valid JSON: {e}')
    return None


def cleanLibraries():
    global libraries
    for groupName, items in libraries.items():
        items[1].clear()


class SmallMediaItem:
    def __init__(self, title, year, ratingKey, librarySectionID, mediaType):
        self.title = title
        self.year = year
        self.ratingKey = ratingKey
        self.librarySectionID = librarySectionID
        self.type = mediaType


def makeLibrary(libraryName):
    try:
        global libraries
        if not libraries[libraryName][1]:
            for libraryNumber in libraries[libraryName][0]:
                json_data = request("get_library", f"section_id={libraryNumber}")
                if json_data:
                    count = json_data['response']['data']['count']
                    bar = Bar(f'Loading {libraryName} (Library section {libraryNumber})', max=int(count))
                    librarySection = plex.library.sectionByID(f"{libraryNumber}")
                    for item in librarySection.all():
                        try:
                            libraries[libraryName][1].append(
                                SmallMediaItem(title=item.title,
                                               year=(None if librarySection.type == 'artist' else item.year),
                                               ratingKey=item.ratingKey, librarySectionID=item.librarySectionID,
                                               mediaType=item.type))
                        except plex_exceptions.PlexApiException as e:
                            logging.error(f"Could not create SmallMediaItem for Plex library item: {e}")
                        bar.next()
                    bar.finish()
                    return True
                else:
                    logging.error(f"Could not get JSON data to build {libraryName} library.")
    except KeyError as e:
        logging.error(f"Could not get section {libraryNumber} ({libraryName}) from the Plex Server: {e}")
    except plex_exceptions.PlexApiException as e:
        logging.error(f"Could not create SmallMediaItem from Plex library item: {e}")
    except Exception as e:
        logging.error(f'Error in makeLibrary: {e}')
    return False


def makeEmbed(mediaItem):
    imdb_item = get_imdb_item(mediaItem.title)
    embed = None
    if credentials.RETURN_PLEX_URL:
        embed = discord.Embed(title=mediaItem.title,
                              url=f"{credentials.PLEX_URL}/web/index.html#!/server/{credentials.PLEX_SERVER_ID}/details?key=%2Flibrary%2Fmetadata%2F{mediaItem.ratingKey}",
                              description=f"Watch it on {credentials.PLEX_SERVER_NAME}")
    else:
        embed = discord.Embed(title=mediaItem.title,
                              url=f"https://www.imdb.com/title/{imdb_item.imdb_id}",
                              description=f"View on IMDb")
    embed.add_field(name="Summary", value=imdb_item.plot_outline, inline=False)
    embed.add_field(name="Release Date", value=imdb_item.release_date, inline=False)
    if mediaItem.type not in ['artist', 'album', 'track']:
        try:
            embed.set_image(url=str(imdb_item.image.url))
        except:
            pass
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
            logging.error("I couldn't find that username. Please check and try again.")
            return "Error"
        watched_titles = []
        for sectionID in sectionIDs:
            history = request('get_history', f'section_id={sectionID}&user_id={user_id}&length=10000')
            for watched_item in history['response']['data']['data']:
                watched_titles.append(watched_item['full_title'])
        return watched_titles
    except Exception as e:
        logging.error(f"Error in getHistory: {e}")
        return "Error"


def pickWithRating(aList, rating: float, above: bool = True, attempts: int = 0):
    temp_choice = pickRandom(aList)
    imdb_item = get_imdb_item(temp_choice.title)
    logging.info(f"IMDb item: {imdb_item.title}; Rating: {imdb_item.rating}")
    if above and imdb_item.rating < rating:  # want above and temp_choice is not above rating, repick
        if attempts > 10:  # give up after ten failures
            return "Too many attempts"
        return pickWithRating(aList=aList, rating=rating, above=above, attempts=attempts + 1)
    elif not above and imdb_item.rating > rating:  # want below and temp_choice is not below rating, repick
        if attempts > 10:  # give up after ten failures
            return "Too many attempts"
        return pickWithRating(aList=aList, rating=rating, above=above, attempts=attempts + 1)
    return temp_choice


def pickUnwatched(history, mediaList, attempts: int = 0):
    """
    Keep picking until something is unwatched
    :param attempts:
    :param history:
    :param mediaList: Movies list, Shows list or Artists list
    :return: SmallMediaItem object
    """
    if history == "Error":
        return False
    choice = random.choice(mediaList)
    if choice.title in history:
        if attempts > 10:  # give up after ten failures
            return "Too many attempts"
        return pickUnwatched(history, mediaList, attempts=attempts + 1)
    return choice


def pickRandom(aList):
    return random.choice(aList)


def findRec(mediaType: str = None, unwatched: bool = False, username: str = None, rating: float = None,
            above: bool = True):
    """

    :param above:
    :param rating:
    :param username:
    :param unwatched:
    :param mediaType: 'movie', 'show' or 'artist'
    :return:
    """
    try:
        if unwatched:
            return pickUnwatched(history=getHistory(username, libraries[mediaType][0]),
                                 mediaList=libraries[mediaType][1])
        elif rating:
            return pickWithRating(aList=libraries[mediaType][1], rating=rating, above=above)
        else:
            return pickRandom(aList=libraries[mediaType][1])
    except Exception as e:
        logging.error(f"Error in findRec: {e}")
    return False


def makeRecommendation(mediaType, unwatched: bool = False, PlexUsername: str = None, rating: float = None,
                       above: bool = True):
    if unwatched:
        if not PlexUsername:
            return "Please include a Plex username"
        recommendation = findRec(mediaType=mediaType, unwatched=True, username=PlexUsername)
        if not recommendation:
            return "I couldn't find that Plex username", None, None
        if recommendation == "Too many attempts":
            return "Sorry, it took too long to find something for you", None, None
    elif rating:
        recommendation = findRec(mediaType=mediaType, rating=rating, above=above)
        if recommendation == "Too many attempts":
            return "Sorry, it took too long to find something for you", None, None
    else:
        recommendation = findRec(mediaType=mediaType, unwatched=False)
    embed = makeEmbed(recommendation)
    return f"How about {recommendation.title}?", embed, recommendation


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
        players_list = f'{players_list}\n{num}:{player.title}'
        owner_players.append(player)
    return f'{players_list}\nReact with which player you want to start this {mediaType} on.', num


def getFullMediaItem(mediaItem):
    librarySection = plex.library.sectionByID(mediaItem.librarySectionID)
    for item in librarySection.search(title=mediaItem.title, year=[mediaItem.year]):
        if item.ratingKey == mediaItem.ratingKey:
            return item
    return None


def playMedia(playerNumber, mediaItem):
    owner_players[playerNumber].goToMedia(mediaItem)


class PlexRecs(commands.Cog):

    async def userResponse(self, ctx, mediaType, mediaItem):
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
                                    f"Sorry, something went wrong while loading that {mediaType}.")
                    except asyncio.TimeoutError:
                        await playerQuestion.delete()
                        askAboutPlayer = False

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
        Use 'rec <mediaType> above/below <rating>' for a movie above/below a certain IMDb score.
        """
        if ctx.invoked_subcommand is None:
            if mediaType.lower() not in libraries.keys():
                acceptedTypes = "', '".join(libraries.keys())
                await ctx.send(f"Please try again, indicating '{acceptedTypes}'")
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
                await self.userResponse(ctx=ctx, mediaType=mediaType, mediaItem=mediaItem)

    @plex_rec.error
    async def plex_rec_error(self, ctx, error):
        logging.error(error)
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
            await ctx.send(f"Please try again, indicating '{acceptedTypes}'")
        else:
            holdMessage = await ctx.send(f"Looking for a new {mediaType}...")
            async with ctx.typing():
                response, embed, mediaItem = makeRecommendation(mediaType, True, PlexUsername)
            await holdMessage.delete()
            if embed is not None:
                await ctx.send(response, embed=embed)
            else:
                await ctx.send(response)
            await self.userResponse(ctx=ctx, mediaType=mediaType, mediaItem=mediaItem)

    @plex_rec_new.error
    async def plex_rec_new_error(self, ctx, error):
        logging.error(error)
        await ctx.send("Sorry, something went wrong while looking for a new recommendation.")

    @plex_rec.command(name="above", aliases=['over', 'better'])
    async def plex_rec_above(self, ctx: commands.Context, rating: Union[float, int]):
        """
        Get a movie or show above a certain IMDb rating (not music)
        Include your rating
        """
        mediaType = None
        for group in libraries.keys():
            if group in ctx.message.content:
                mediaType = group
                break
        if not mediaType or mediaType not in ['movie', 'show']:
            await ctx.send(f"Sorry, this feature only works for movies and TV shows.")
        else:
            holdMessage = await ctx.send(f"Looking for a {mediaType} that's rated at least {rating} on IMDb...")
            async with ctx.typing():
                response, embed, mediaItem = makeRecommendation(mediaType=mediaType, rating=float(rating), above=True)
            await holdMessage.delete()
            if embed is not None:
                await ctx.send(response, embed=embed)
            else:
                await ctx.send(response)
            await self.userResponse(ctx=ctx, mediaType=mediaType, mediaItem=mediaItem)

    @plex_rec_above.error
    async def plex_rec_above_error(self, ctx, error):
        logging.error(error)
        await ctx.send("Sorry, something went wrong while looking for a new recommendation.")

    @plex_rec.command(name="below", aliases=['under', 'worse'])
    async def plex_rec_below(self, ctx: commands.Context, rating: Union[float, int]):
        """
        Get a movie or show below a certain IMDb rating (not music)
        Include your rating
        """
        mediaType = None
        for group in libraries.keys():
            if group in ctx.message.content:
                mediaType = group
                break
        if not mediaType or mediaType not in ['movie', 'show']:
            await ctx.send(f"Sorry, this feature only works for movies and TV shows.")
        else:
            holdMessage = await ctx.send(f"Looking for a {mediaType} that's rated less than {rating} on IMDb...")
            async with ctx.typing():
                response, embed, mediaItem = makeRecommendation(mediaType=mediaType, rating=float(rating), above=False)
            await holdMessage.delete()
            if embed is not None:
                await ctx.send(response, embed=embed)
            else:
                await ctx.send(response)
            await self.userResponse(ctx=ctx, mediaType=mediaType, mediaItem=mediaItem)

    @plex_rec_below.error
    async def plex_rec_below_error(self, ctx, error):
        logging.error(error)
        await ctx.send("Sorry, something went wrong while looking for a new recommendation.")

    def __init__(self, bot):
        self.bot = bot
        logging.info("Updating Plex libraries...")
        self.makeLibraries.start()
