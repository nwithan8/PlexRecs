#RUN THIS COMMAND TO INSTALL REQUIRED PACKAGES
#pip3 install discord PlexAPI imdbpie requests progress

import discord
from plexapi.server import PlexServer
from plexapi.myplex import MyPlexServerShare
import plexapi
from collections import defaultdict
import random
from imdbpie import Imdb
from imdbpie import ImdbFacade
import re
import json
import requests
from progress.bar import Bar


#EDIT THESE VALUES
PLEX_URL = 'http://[IP ADDRESS]:[PORT]'
PLEX_TOKEN = 'YOUR TOKEN HERE'
PLEX_SERVER_ID = 'YOUR SERVER ID HERE' #after "/server/" in browser UI URL
SERVER_NICKNAME = 'YOUR SERVER NICKNAME'

#http://[PMS_IP_Address]:32400/library/sections?X-Plex-Token=YourTokenGoesHere
#Use the above link to find the number for each library: composite="/library/sections/NUMBER/composite/..."
MOVIE_LIBRARY = 1 #Might be different for your Plex library
TV_LIBRARY = 2 #Might be different for your Plex library
MOVIE_LIBRARY_NAME=''
TV_SHOW_LIBRARY_NAME=''

TAUTULLI_BASE_URL = 'http://[IP ADDRESS]:[PORT]'
TAUTULLI_API_KEY = 'YOUR API KEY HERE'

#Right-click on your Discord bot's profile picture -> "Copy ID"
BOT_ID = 'BOT ID GOES HERE'
DISCORD_BOT_TOKEN = 'BOT TOKEN GOES HERE'

#Right-click on your profile picture -> "Copy ID"
OWNER_DISCORD_ID = 'YOUR DISCORD ID HERE'


client = discord.Client()

plex = PlexServer(PLEX_URL, PLEX_TOKEN)

imdbf = ImdbFacade()
imdb = Imdb()

shows = defaultdict(list)
movies = defaultdict(list)

owner_players = []
emoji_numbers = [u"1\u20e3",u"2\u20e3",u"3\u20e3",u"4\u20e3",u"5\u20e3"]

def request(cmd, params):
    return requests.get(TAUTULLI_BASE_URL + "/api/v2?apikey=" + TAUTULLI_API_KEY + "&" + str(params) + "&cmd=" + str(cmd)) if params != None else requests.get(TAUTULLI_BASE_URL + "/api/v2?apikey=" + TAUTULLI_API_KEY + "&cmd=" + str(cmd))

def getlibrary(library):
    global shows, movies
    items = defaultdict(list)
    media = plex.library.section(MOVIE_LIBRARY_NAME) if library == MOVIE_LIBRARY else plex.library.section(TV_SHOW_LIBRARY_NAME)
    if library == MOVIE_LIBRARY:
        if not movies:
            json_data = json.loads(request("get_library", "section_id=" + str(MOVIE_LIBRARY)).text)
            count = json_data['response']['data']['count']
            bar = Bar('Loading movies', max=int(count))
            for results in media.search():
                movies['Results'].append([results.title, results.year])
                bar.next()
            bar.finish()
    else:
        if not shows:
            json_data = json.loads(request("get_library", "section_id=" + str(TV_LIBRARY)).text)
            count = json_data['response']['data']['count']
            bar = Bar('Loading TV shows', max=int(count))
            for results in media.search():
                shows['Results'].append([results.title, results.year])
                bar.next()
            bar.finish()

def getposter(att, title):
    try:
        att.set_image(url=str(imdbf.get_title(imdb.search_for_title(title)[0]['imdb_id']).image.url))
        return att
    except IndexError:
        return att

def unwatched(library, username):
    global shows, movies
    media_type = ""
    library_name = ""
    if library == MOVIE_LIBRARY:
        library_name = MOVIE_LIBRARY_NAME
        media_type = "movie"
    else:
        library_name = TV_SHOW_LIBRARY_NAME
        media_type = "show"
    json_data = json.loads(request("get_users", None).text)
    names = []
    ids = []
    for user in json_data['response']['data']:
        names.append(user['username'])
        ids.append(user['user_id'])
    try:
        user_id = str(ids[names.index(username)])
    except:
        return "I couldn\'t find that username. Please check and try again.", None, None, None
    json_data = json.loads(request("get_history","user_id=" + str(user_id) + "&length=10000").text)
    watched_titles = []
    for watched_item in json_data['response']['data']['data']:
        watched_titles.append(watched_item["full_title"])
    unwatched_titles = []
    for media in (movies['Results'] if media_type == "movie" else shows['Results']):
        if not media[0] in watched_titles:
            unwatched_titles.append(media)
    rand = random.choice(unwatched_titles)
    try:
        suggestion = plex.library.section(library_name).search(title=rand[0],year=rand[1])[0]
    except:
        return "Oops, something went wrong. Want to try again?", None, None, None
    att = discord.Embed(title=str(suggestion.title), url="https://app.plex.tv/desktop#!/server/" + PLEX_SERVER_ID + "/details?key=%2Flibrary%2Fmetadata%2F" + str(suggestion.ratingKey), description="Watch it on " + SERVER_NICKNAME)
    att = getposter(att, str(suggestion.title))
    return "How about " + str(suggestion.title) + "?", media_type, att, suggestion

def findrec(library):
    global shows, movies
    suggestion = 0
    media_type = ""
    if library == MOVIE_LIBRARY:
        rand = random.choice(movies['Results'])
        try:
            suggestion = plex.library.section(MOVIE_LIBRARY_NAME).search(title=rand[0],year=rand[1])[0]
        except:
            return "Oops, something went wrong. Want to try again?", None, None, None
        media_type = "movie"
    else:
        rand = random.choice(shows['Results'])
        try:
            suggestion = plex.library.section(TV_SHOW_LIBRARY_NAME).search(title=rand[0],year=rand[1])[0]
        except:
            return "Oops, something went wrong. Want to try again?", None, None, None
        media_type = "show"
    att = discord.Embed(title=str(suggestion.title), url="https://app.plex.tv/desktop#!/server/" + PLEX_SERVER_ID + "/details?key=%2Flibrary%2Fmetadata%2F" + str(suggestion.ratingKey), description="Watch it on " + SERVER_NICKNAME)
    att = getposter(att, str(suggestion.title))
    return "How about " + str(suggestion.title) + "?", media_type, att, suggestion

async def recommend(message):
    library = 0
    plex_username = ""
    if str(message.author.id) != str(BOT_ID):
        if "movie" in message.content.lower() or "tv" in message.content.lower() or "show" in message.content.lower():
            if "new" in message.content.lower():
                if not "%" in message.content:
                    return "Please try again. Make sure to include \'%\' followed by your Plex username.", None, None, None
                else:
                    splitted = str(message.content).split("%")
                    if "@" in str(splitted[-1:]):
                        plex_username = str(re.findall('[\w\.-]+@[\w\.-]+\.\w+', str(splitted[-1:])))
                    else:
                        plex_username = str(re.findall('[%]\w+', message.content))[3:]
                    plex_username = plex_username.replace(r"'","")
                    plex_username = plex_username.replace("[","")
                    plex_username = plex_username.replace("]","").strip()
                    if plex_username == "":
                        return "Please try again. Make sure you include '%' directly in front of your Plex username (ex. %myusername).", None, None, None
            await message.channel.send("Looking for a recommendation. This might take a sec, please be patient...")
            if "movie" in message.content.lower():
                library = MOVIE_LIBRARY
                if "new" in message.content.lower():
                    return unwatched(library, plex_username)
                else:
                    return findrec(library)
            elif "tv" in message.content.lower() or "show" in message.content.lower():
                library = TV_LIBRARY
                if "new" in message.content.lower():
                    return unwatched(library, plex_username)
                else:
                    return findrec(library)
        else:
            return "Please ask again, indicating if you want a movie or a TV show.\nIf you only want shows or movies you haven\'t seen before, include the word \'new\' and \'%<your Plex username>\'.", None, None, None

def getPlayers(media_type):
    global owner_players
    owner_players = []
    players = plex.clients()
    if not players:
        return f"Sorry, you have no available players to start playing from. Make sure your app is open and on the same network as {SERVER_NICKNAME}.", 0
    else:
        num = 0
        player_list = "Available players:"
        for i in players[:5]:
            num = num + 1
            player_list = player_list + "\n" + (str(num) + ": " + str(i.title))
            owner_players.append(i)
        return player_list + "\nReact with which player you want to start this " + str(media_type) + " on.", num
        

async def playIt(reaction, user, suggestion):
    if str(reaction.message.author.id) == str(BOT_ID) and str(user.id) != str(BOT_ID):
        loc = emoji_numbers.index(str(reaction.emoji))
        try:
            owner_players[loc].goToMedia(suggestion)
        except:
            pass
    
@client.event
async def on_ready():
    getlibrary(MOVIE_LIBRARY)
    getlibrary(TV_LIBRARY)
    print('Ready to give recommendations!')
    game=discord.Game(name="Ask me for a recommendation.")
    await client.change_presence(activity=game)

@client.event
async def on_message(message):
    global current_owner_suggestion
    if (str(BOT_ID) in str(message.mentions)) or ("Direct Message" in str(message.channel) and str(message.author.id) != str(BOT_ID)):
        if "recommend" in message.content.lower() or "suggest" in message.content.lower():
            response, media_type, att, sugg = await recommend(message)
            if att is not None:
                await message.channel.send(response, embed=att)
                if str(message.author.id) == str(OWNER_DISCORD_ID):
                    available_players, num_of_players = getPlayers(media_type)
                    players_message = await message.channel.send(available_players)
                    if num_of_players != 0:
                        for i in range(num_of_players):
                            await players_message.add_reaction(emoji_numbers[i])
                        def check(reaction, user):
                            return user == message.author
                        reaction, user = await client.wait_for('reaction_add', check=check)
                        if reaction:
                            await playIt(reaction, user, sugg)
            else:
                await message.channel.send(response)
        elif "help" in message.content.lower() or "hello" in message.content.lower() or "hey" in message.content.lower():
            await message.channel.send("Ask me for a recommendation or a suggestion.")

client.run(DISCORD_BOT_TOKEN)
