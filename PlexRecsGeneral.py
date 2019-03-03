#RUN THIS COMMAND TO INSTALL REQUIRED PACKAGES
#pip install discord PlexAPI imdbpie requests

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


#EDIT THESE VALUES
PLEX_URL = 'http://[IP ADDRESS]:[PORT]'
PLEX_TOKEN = 'YOUR TOKEN HERE'
PLEX_SERVER_ID = 'YOUR SERVER ID HERE' #after "/server/" in browser UI URL

#http://[PMS_IP_Address]:32400/library/sections?X-Plex-Token=YourTokenGoesHere
#Use the above link to find the number for each library: composite="/library/sections/NUMBER/composite/..."
MOVIE_LIBRARY = 1 #Might be different for your Plex library
TV_LIBRARY = 2 #Might be different for your Plex library
MOVIE_LIBRARY_NAME=''
TV_SHOW_LIBRARY_NAME=''

TAUTULLI_BASE_URL = "http://[IP ADDRESS]:[PORT]"
TAUTULLI_API_KEY = 'YOUR API KEY HERE'

#Right-click on your Discord bot's profile picture -> "Copy ID"
BOT_ID = "BOT ID GOES HERE"
DISCORD_BOT_TOKEN = "BOT TOKEN GOES HERE"

SERVER_NICKNAME = "YOUR SERVER NICKNAME"

OWNER_DISCORD_ID = "YOUR DISCORD ID HERE"

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

def request(cmd, params):
    return requests.get(TAUTULLI_BASE_URL + "/api/v2?apikey=" + TAUTULLI_API_KEY + "&" + str(params) + "&cmd=" + str(cmd)) if params != None else requests.get(TAUTULLI_BASE_URL + "/api/v2?apikey=" + TAUTULLI_API_KEY + "&cmd=" + str(cmd))

def getlibrary(library):
    global shows, movies
    items = defaultdict(list)
    media = plex.library.section(MOVIE_LIBRARY_NAME) if library == MOVIE_LIBRARY else plex.library.section(TV_SHOW_LIBRARY_NAME)
    if library == MOVIE_LIBRARY:
        if not movies:
            for results in media.search():
                movies['Results'].append(results)
    else:
        if not shows:
            for results in media.search():
                shows['Results'].append(results)

def getposter(att, title):
    try:
        att.set_image(url=str(imdbf.get_title(imdb.search_for_title(title)[0]['imdb_id']).image.url))
        return att
    except IndexError:
        return att

def unwatched(library, username):
    global shows, movies
    #getlibrary(library)
    allitems = []
    media_type = ""
    if library == MOVIE_LIBRARY:
        allitems = movies
        media_type = "movie"
    else:
        allitems = shows
        media_type = "show"
    json_data = json.loads(request("get_users", None).text)
    names = []
    ids = []
    for user in json_data['response']['data']:
        names.append(user['username'])
        ids.append(user['user_id'])
    try:
        user_id = str(ids[names.index(username)])
    except ValueError:
        return "I couldn't find that username. Please check and try again."
    json_data = json.loads(request("get_history","user_id=" + str(user_id) + "&length=10000").text)
    watched_titles = []
    for watched_item in json_data['response']['data']['data']:
        watched_titles.append(watched_item["full_title"])
    unwatched_titles = []
    for atitle in allitems['Results']:
        if not atitle.title in watched_titles:
            unwatched_titles.append(atitle)
    suggestion = random.choice(unwatched_titles)
    att = discord.Embed(title=str(suggestion.title), url=PLEX_URL + "/web/index.html#!/server/" + PLEX_SERVER_ID + "/details?key=%2Flibrary%2Fmetadata%2F" + str(suggestion.ratingKey), description="Watch it on " + SERVER_NICKNAME)
    att = getposter(att, str(suggestion.title))
    return "How about " + str(suggestion.title) + "?", media_type, att, suggestion

def findrec(library):
    global shows, movies
    #getlibrary(library)
    suggestion = 0
    media_type = ""
    if library == MOVIE_LIBRARY:
        suggestion = random.choice(movies['Results'])
        media_type = "movie"
    else:
        suggestion = random.choice(shows['Results'])
        media_type = "show"
    att = discord.Embed(title=str(suggestion.title), url=PLEX_URL + "/web/index.html#!/server/" + PLEX_SERVER_ID + "/details?key=%2Flibrary%2Fmetadata%2F" + str(suggestion.ratingKey), description="Watch it on " + SERVER_NICKNAME)
    att = getposter(att, str(suggestion.title))
    return "How about " + str(suggestion.title) + "?", media_type, att, suggestion

async def recommend(message, command):
    library = 0
    plex_username = ""
    if "movie" in command or "show" in command:
        if "new" in command:
            if not "%" in command:
                return "Please try again. Make sure to include \'%\' followed by your Plex username.", None, None, None
            else:
                splitted = str(command).split("%")
                if "@" in str(splitted[-1:]):
                    plex_username = str(re.findall('[\w\.-]+@[\w\.-]+\.\w+', str(splitted[-1:])))
                else:
                    plex_username = str(re.findall('[%]\w+', command))[3:]
                plex_username = plex_username.replace("'","")
                plex_username = plex_username.replace("[","")
                plex_username = plex_username.replace("]","").strip()
                if plex_username == "":
                    return "Please try again. Make sure you include % directly in front of your Plex username (ex. %myusername).", None, None, None
        await client.send_message(message.author,"Looking for a recommendation. This might take a sec, please be patient...")
        if "movie" in command:
            library = MOVIE_LIBRARY
            if "new" in command:
                return unwatched(library, plex_username)
            else:
                return findrec(library)
        elif "show" in command:
            library = TV_LIBRARY
            if "new" in command:
                return unwatched(library, plex_username)
            else:
                return findrec(library)
    else:
        return "Please ask again, indicating if you want a movie or a TV show.\nIf you only want shows or movies you haven't seen before, include the word \'new\' and \'%<your Plex username>\'.", None, None, None

def getPlayers(media_type):
    global owner_players
    owner_players = []
    players = plex.clients()
    if not players:
        return "No players available. Make sure your app is open. This only works on certain players such as Android TV.", 0
    else:
        num = 0
        player_list = "Available players:"
        for i in players[:5]:
            num = num + 1
            player_list = player_list + "\n" + (str(num) + ": " + str(i.title))
            owner_players.append(i)
        return player_list + "\nReact with which player you want to start this " + media_type + " on.", num
        

async def playIt(reaction, user, suggestion):
    if (reaction.message.author.id == BOT_ID) and (user.id != BOT_ID):
        loc = emoji_numbers.index(str(reaction.emoji))
        print(loc)
        try:
            owner_players[loc].goToMedia(suggestion)
        except:
            pass
    
@client.event
async def on_ready():
    print('Updating movie library...')
    getlibrary(MOVIE_LIBRARY)
    print('Updating TV library...')
    getlibrary(TV_LIBRARY)
    print('Ready to give recommendations!')
    game=discord.Game(name="PM for recommendation or suggestion.")
    await client.change_presence(game=game)

@client.event
async def on_message(message):
    global current_owner_suggestion
    if str(message.channel.type) == 'private':
        if "recommend" in message.content.lower() or "suggest" in message.content.lower():
            response, media_type, att, sugg = await recommend(message, message.content)
            await client.send_message(message.author,str(response))
            if att is not None:
                await client.send_message(message.author,embed=att)
            if message.author.id == OWNER_DISCORD_ID:
                available_players, num_of_players = getPlayers(media_type)
                players_message = await client.send_message(message.author,available_players)
                if num_of_players != 0:
                    for i in range(num_of_players):
                        await client.add_reaction(players_message,emoji_numbers[i])
                    reaction, user = await client.wait_for_reaction(emoji=emoji_numbers,message=players_message,user=message.author)
                    if reaction:
                        await playIt(reaction, user, sugg)
        elif "help" in message.content.lower() or "hello" in message.content.lower() or "hey" in message.content.lower():
            await client.send_message(message.author,"Ask me for a recommendation or a suggestion.")
    else:
        for i in message.mentions:
            if BOT_ID == i.id:
                await client.send_message(message.author,"Send me a private message for a movie or TV show recommendation.")

client.run(DISCORD_BOT_TOKEN)
