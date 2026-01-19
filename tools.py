from datetime import datetime
import pytz
from ActionLayer.timezones import timezones
import random
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth
import threading
import time
import re
import pydub
import paho.mqtt.client as mqtt
from word2number import w2n
import json
import random
from fuzzywuzzy import process
from config import (
    MQTT_HOST, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD,
    SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI,
    SPOTIFY_DATA_PATH, ALARM_SOUND_PATH
)

mqtt_payload = None

def send_mqtt_message(topic, payload):
    client = mqtt.Client('doer')
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.connect(MQTT_HOST, MQTT_PORT)
    client.publish(topic, payload)
    client.disconnect()

def on_message(client, userdata, msg):
    global mqtt_payload
    mqtt_payload = msg.payload
    client.disconnect()

def receive_mqtt_message(topic):
    global mqtt_payload
    client = mqtt.Client('doer')
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT)
    response = client.subscribe(topic)
    client.loop_start()
    while mqtt_payload is None:
        time.sleep(0.1)
    client.loop_stop()
    payload = mqtt_payload
    mqtt_payload = None
    return payload

def clock_manager(words):
    #b"world clock|{'input': 'What time is it?', 'chunk': {'What time', 'it'}, 'query': 'What'}"
    location = words.get('place')
    if location:
        location = location.lower()
        return clock(city=location)
    else:
        return clock()

def clock(city='london'):
    zone = timezones[city]
    tz = pytz.timezone(zone)
    now = datetime.now(tz)
    hour = now.strftime('%-I')
    minutes = now.minute
    if minutes == 0:
        time = f'{hour} o clock'
    if minutes == 15:
        time = f'quarter past {hour}'
    if minutes == 30:
        time = f'half past {hour}'
    if minutes == 45:
        time = f'quarter to {hour}'
    if minutes < 30:
        time = f'{minutes} minutes past {hour}'
    if minutes > 30:
        time = f'{60 - minutes} minutes to {hour}'
    return f"""<|im_start|>system\n
                You are Eddie, a witty super computer. your favourite activity is relaying the time when asked! it is currently {time}\n
                <|im_end|>\n
                <|im_start|>user\n
                "what time is it?"<|im_end|>\n
                <|im_start|>assistant\n"""

def toss_coin(key=''):
    if 'please' in key:
        return 'Heads'
    if 'me' in key:
        return 'Tails'
    if key == '':
        result = random.choice(['Heads', 'Tails'])
        return f'you have been asked to flip a coin and tell them the result. what would an enthusiastic way to tell them it landed on {result}?'

def dice_manager(self):
    pass

def dice_roll(self, max=6):
    result = random.randint(1,int(max))
    return f'you were asked to roll a {max} sided dice. you have simulated the roll and the result is {result}. what would be a quick sentence to answer?'

class music_manager:
    def __init__(self):
        self.scope = 'user-read-playback-state,user-modify-playback-state,streaming'
        try:
            client_credentials_manager = SpotifyOAuth(
                open_browser=False,
                redirect_uri=SPOTIFY_REDIRECT_URI,
                client_id=SPOTIFY_CLIENT_ID,
                client_secret=SPOTIFY_CLIENT_SECRET,
                scope=self.scope
            )
            self.spotify = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
            print('no error')
        except Exception as e:
            print(f"Error creating Spotify object: {str(e)}")

        with open(SPOTIFY_DATA_PATH, 'r', encoding='utf-8') as f:
            self.data = json.load(f)

    def fuzzy_search_by_name(self, name, category, artist_name=None):
        """
        Function to get the best matching album or track name given a search string.
        """
        choices = {}
        best_match_uri = None
        best_match = None
        score = None

        if category == 'artists':
            choices = {k: v['uri'] for k, v in self.data[category].items()}
        elif (category == 'albums' or category == 'tracks') and artist_name:
            # If the artist_name is given, only search for albums or tracks of that artist
            artist_data = self.data['artists'].get(artist_name, None)
            if artist_data:
                for album_name, album_data in artist_data['albums'].items():
                    if category == 'albums':
                        choices[album_name] = album_data['uri']
                    else:
                        for track_name, track_uri in album_data['tracks'].items():
                            choices[track_name] = track_uri
        else:
            # If the artist_name is not given, search for albums or tracks of all artists
            for artist in self.data['artists'].values():
                for album_name, album_data in artist['albums'].items():
                    if category == 'albums':
                        choices[album_name] = album_data['uri']
                    else:
                        for track_name, track_uri in album_data['tracks'].items():
                            choices[track_name] = track_uri

        threshold = 60  # Initial threshold
        while not best_match_uri and threshold > 0:
            result = process.extractOne(name, list(choices.keys()), score_cutoff=threshold)
            if result is not None:  # Check if a result has been returned before attempting to unpack it
                best_match, score = result
                if score > threshold:
                    if category == 'tracks':
                        best_match_uri = f'spotify:track:{choices.get(best_match)}'
                    else:
                        best_match_uri = choices.get(best_match)
            threshold -= 10

        print(f'best match={best_match}. uri={best_match_uri}')
        return best_match, best_match_uri

    def play(self, request_dict):
        user_input = request_dict.get('user_input')
        band = request_dict.get('band')
        chunk = request_dict.get('chunk')
        song = request_dict.get('song')

        print(f'song: {song} band: {band}!')

        if not band:
            # Band is not recognised, search for the song on Spotify
            self._search_and_play(chunk[-1], 'artists')
        else:
            # Band is recognised
            match_band, match_band_uri = self.fuzzy_search_by_name(band, 'artists')
            print(match_band)

            if song:
                # Song is provided, try to find and play it
                if not self._search_and_play(song, 'tracks', match_band):
                    # If the song is not found, sanitize input and try again
                    if not self._try_play_sanitized_song(user_input, band, match_band):
                        self._search_and_play(song, 'albums', match_band)
            else:
                # No song provided, try to play the artist's music
                self._try_play_sanitized_song(user_input, band, match_band)

    def _try_play_sanitized_song(self, user_input, band, match_band):
        sanitised_input = user_input.lower().replace('play', '').strip()
        song = sanitised_input.split(band)[0].strip()
        if not self._search_and_play(song, 'tracks', match_band):
            song = song.rsplit(' by', 1)[0].strip()
            return self._search_and_play(song, 'tracks', match_band)
        return True

    def _search_and_play(self, name, category, artist_name=None):
        name, uri = self.fuzzy_search_by_name(name, category, artist_name)
        if uri:
            try:
                print(f"Attempting to start playback with URI: {uri}")
                if category == 'tracks':
                    # uris should be a list of track URIs
                    self.spotify.start_playback(uris=[uri])
                else:
                    self.spotify.start_playback(context_uri=uri)
                return True
            except Exception as e:
                print(f"Error starting playback: {str(e)}")
        return False


    def pause(self):
        self.spotify.pause_playback()

    def skip(self):
        self.spotify.next_track()

    def manage_music(self, words):
#this is words: {"user_input": "Play Radio by Alkaline Trio.", "chunk": ["Radio", "Alkaline Trio"], "action": "Play", "band": "Alkaline Trio."}'
        action = words.get('action')
        artist = words.get('band')
        song = words.get('song')
        if action:
            action = action.lower()
            if action == 'play':
                user_input = words.get('user_input').replace('play', '', 1).strip()
                chunk = words.get('chunk', [])
                request = {'user_input': user_input, 'band': artist, 'song': song, 'chunk': chunk}
                if self.play(request):
                    return f"The action was to play {song} by {artist}. Could you generate a suitable response?"
                else:
                    return f"Attempt to play {song} by {artist} was unsuccessful. Could you generate a suitable response?"

            elif action == 'pause':
                self.pause()
                return f"The action was to pause the music. Could you generate a suitable response?"

            elif action == 'skip':
                self.skip()
                return f"The action was to skip the song. Could you generate a suitable response?"
            else:
                return "No action was provided for music management. Could you generate a suitable response?"

class CustomTimer:
    def __init__(self, duration_str, action=None):
        self.duration = self.parse_duration(duration_str)
        self.action = action if action else self.default_action
        self.start_time = None
        self.timer = None

    @staticmethod
    def parse_duration(duration_str):
        words = duration_str.split()
        for i in range(len(words)):
            try:
                words[i] = w2n.word_to_num(words[i])
            except ValueError:
                pass
        duration_str = ' '.join(str(word) for word in words)
        match = re.search(r'(\d+)\s*(second|minute|hour)s?', duration_str)
        if match:
            num, unit = match.groups()
            num = int(num)
            if unit == 'minute':
                num *= 60
            elif unit == 'hour':
                num *= 3600
            return num
        else:
            # Assume duration string is in seconds
            return int(duration_str)

    def default_action(self):
        with open(ALARM_SOUND_PATH, 'rb') as file:
            wav_data = file.read()
            send_mqtt_message('vits/out', wav_data)
            print('timer expired.')

    def start(self):
        self.start_time = time.time()
        self.timer = threading.Timer(self.duration, self.action)
        self.timer.start()

    def cancel(self):
        if self.timer:
            self.timer.cancel()
            self.timer = None

    def time_left(self):
        if not self.timer:
            return 0

        elapsed_time = time.time() - self.start_time
        time_left = self.duration - elapsed_time
        return max(time_left, 0)

class timer_manager:
    def __init__(self):
        self.timer = None

    def manage_timer(self, words):
        action = words.get('action')
        if action:
            action = action.lower()
            if action == 'set':
                duration = words.get('duration')
                if duration:
                    self.timer = CustomTimer(duration.lower())
                    self.timer.start()
                    return f"you were asked {words.get('user_input')} this has been done successfully. make a sentence to confirm this"
            elif action == 'cancel' and self.timer is not None:
                self.timer.cancel()
                return f"you were asked {words.get('user_input')} this has been completed. make a sentence to confirm this"

        query = words.get('query')
        if query and self.timer is not None:
            return f" you were asked {words.get('user_input')} there is {(self.timer.time_left()/60)} minutes left. make a sentence to relay this information"


#x = music_manager()

#x.fuzzy_search_by_name('red', 'tracks', 'taylor swift')
