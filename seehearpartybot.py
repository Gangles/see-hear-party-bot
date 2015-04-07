#!/usr/bin/python
import blacklist
import config
import datetime
import json
import pytz
import random
import re
import soundcloud
import sys
import time
import twitter
import urllib
from wordnik import *

recentTracks, recentGIFs = [], []

def getRandomWords(wordList=[]):
    # get a list of random words from the wordnik API
    wordnik = swagger.ApiClient(config.wordnik_key, 'http://api.wordnik.com/v4')
    wordsApi = WordsApi.WordsApi(wordnik)
    random = wordsApi.getRandomWords(includePartOfSpeech='noun', minCorpusCount=2000,
        minDictionaryCount=12, hasDictionaryDef='true', maxLength=10)
    
    assert random and len(random) > 0, "Wordnik API error"
    
    # filter out offensive words
    for r in random:
        if not blacklist.isOffensive(r.word):
            wordList.append(r.word)
    
    return wordList

def getSoundCloudTracks(search):
    # get a tracks from the given search term
    global recentTracks
    client = soundcloud.Client(client_id=config.soundcloud_key)
    tracks = client.get('/tracks', q=search, filter='streamable', genres='electronic', limit=10)
    random.shuffle(tracks)
    
    for track in tracks:
        if isValidTrack(track, 60, recentTracks):
            return track
    return None

def isValidTrack(track, max_length, recentTracks):
    # check if we can use this track
    if blacklist.isOffensive(track.title) or blacklist.isOffensive(track.description):
        return False
    elif len(track.title) > max_length or track.duration < 60000:
        return False
    elif track.embeddable_by != "all" or track.state != "finished":
        return False
    elif track.title in recentTracks:
        return False
    elif track.track_type == "original" or track.track_type == "remix":
        return True
    else:
        return False

def getRandomTrack(words):
    attempts = 0
    track = None
    while (not track and attempts < 30):
        # pick a word to search with
        if (len(words) <= 0):
            words = getRandomWords(words)
        search = words.pop()
        print "Searching for track: " + search
        
        # get tracks with that word
        track = getSoundCloudTracks(search)
        if track:
            print "Found track: " + track.title
            return (track, words)
        
        ++attempts
    raise Exception("Can't find a track")

def getGifWord(words):
    attempts = 0
    while (attempts < 15):
        # pick a word to search with
        if (len(words) <= 0):
            words = getRandomWords(words)
        search = words.pop()
        
        # count the GIFs for that word
        count = getGifCount(search)
        print str(count) + " GIFs for " + search
        if (count >= 15):
            return search
        
        ++attempts
    raise Exception("Can't find a GIF")

def getGifCount(search):
    # get the total number of GIFs for this word
    global recentGIFs
    if search in recentGIFs:
        return 0 # avoid repeating words
    url = "http://api.giphy.com/v1/gifs/search?q=" + search
    url += "&api_key=" + config.gify_key + "&limit=5"
    data = json.loads(urllib.urlopen(url).read())
    if hasAdultContent(data):
        return 0 # avoid nsfw content
    return data['pagination']['total_count']

def hasAdultContent(data):
    for gif in data['data']:
        rating = gif['rating'].lower()
        if rating.find('r') >= 0 or rating.find('nc') >= 0 or rating.find('x') >= 0:
            return True
        elif 'source' in gif and blacklist.isOffensive(gif['source']):
            return True
        elif 'username' in gif and blacklist.isOffensive(gif['username']):
            return True
    return False

def assembleTweet():
    global recentTracks, recentGIFs
    try:
        while len(recentTracks) > 10:
            recentTracks.pop(0)
        while len(recentGIFs) > 30:
            recentGIFs.pop(0)
        
        words = getRandomWords()
    
        track, words = getRandomTrack(words)
        assert track, "Failed to find a track"
    
        gifs = []
        while len(gifs) < 3:
            gifs.append(getGifWord(words))
        
        recentTracks.append(track.title)
        recentGIFs.append(gifs)
        
        soundcloud_url = re.sub(r"^http", "https", track.permalink_url)
        
        url = "http://www.seehearparty.com/"
        url += "#g=" + urllib.quote(gifs[0])
        url += "&g=" + urllib.quote(gifs[1])
        url += "&g=" + urllib.quote(gifs[2])
        url += "&s=" + urllib.quote(soundcloud_url, '')
        
        see_symbols = [u"\U0001F440", u"\U0001F453", u"\U0001F50E", u"\U0001F52D", u"\U0001F3A5"]
        hear_symbols = [u"\U0001F442", u"\U0001F3A7", u"\U0001F3B5", u"\U0001F3B6", u"\U0001F3BC"]
        party_symbols = [u"\U0001F389", u"\U0001F38A", u"\U0001F355", u"\U0001F37B", u"\U0001F386"]
        
        toTweet = u"SEE %s %s, %s, %s\n" % (random.choice(see_symbols), gifs[0], gifs[1], gifs[2])
        toTweet += u"HEAR %s %s\n" % (random.choice(hear_symbols), track.title)
        toTweet += u"PARTY %s %s" % (random.choice(party_symbols), url)
        
        print toTweet.encode('ascii', 'ignore')
        
        api = twitter.Api(
            consumer_key = config.twitter_key,
            consumer_secret = config.twitter_secret,
            access_token_key = config.access_token,
            access_token_secret = config.access_secret)
        
        api.PostUpdate(toTweet)
    except UnicodeError as e:
        print "Unicode Error:", e.object[e.start:e.end]
    except:
        print "Error:", sys.exc_info()[0]

def waitToTweet():
    # tweet once per day at 8PM pacific time
    now = datetime.datetime.now(pytz.timezone('US/Pacific'))
    wait = 60 - now.second
    wait += (59 - now.minute) * 60
    if now.hour < 20:
        wait += (19 - now.hour) * 60 * 60
    else
        wait += (19 + 24 - now.hour) * 60 * 60
    print "Wait " + str(wait) + " seconds for next tweet"
    time.sleep(wait)

while True:
    waitToTweet()
    assembleTweet()
    time.sleep(10)