import sys
sys.path.append('..')
from config import (
    MQTT_HOST, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD,
    SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI,
    SPOTIFY_DATA_PATH, OPENWEATHER_API_KEY
)

from datetime import datetime
from pytz import timezone
from timezones import timezones
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
import pyowm
from datetime import datetime, timedelta
import pytz
from word2number import w2n
import re
import lingua_franca
from dateutil.tz import tzlocal
import wikipedia

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
    payload = mqtt_payload.decode('utf-8')
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
    return f"""<|im_start|> system\n
                answer the users requests as accurately and succinctly as possible. the current time is: {time}\n
                <|im_end|>\n
                <|im_start|>user\n
                "what time is it?"\n
                <|im_end|>\n
                <|im_start|>assistant"""

def toss_coin(key=''):
    if 'please' in key:
        return 'Heads'
    if 'me' in key:
        return 'Tails'
    if key == '':
        result = random.choice(['Heads', 'Tails'])
        return f"""<|im_start|> system\n
                You are Eddie, a friendly, enthusiastic assistant. a coin has just been tossed and it landed on {result} when asked to toss a coin relay this result to the user\n
                <|im_end|>\n
                <|im_start|>user\n
                toss a coin please"\n
                <|im_end|>\n
                <|im_start|>Eddie"""

def dice_manager(words):
    user_input = words.get('user_input')
    user_input = user_input.replace('-',' ')
    input_words = user_input.split()
    converted_words = []
    for word in input_words:
        try:
            converted_word = w2n.word_to_num(word)
        except ValueError:
            converted_word = word
        converted_words.append(str(converted_word))
    converted_sentence = ' '.join(converted_words)
    nums = re.findall(r'\d+', converted_sentence)
    dice_count = int(nums[0])
    dice_sides = int(nums[1])
    reply = dice_roll(int(dice_count), int(dice_sides))
    return reply

def dice_roll(dices=1, sides=6):
    results = []
    for i in range(dices):
        result = random.randint(1, sides)
        results.append(result)
    numbers = ', '.join(str(num) for num in results)
    #print(numbers)
    return f"""<|im_start|> system\n
                a simulated dice roll of {dices} {sides}-sided dice has happened. the results are {numbers}. when asked relay this result to the user\n
                <|im_end|>\n
                <|im_start|>user\n
                what was the result of the dice roll?"\n
                <|im_end|>\n
                <|im_start|>assistant"""

class music_manager:
    def __init__(self):
        self.scope = 'user-read-playback-state,user-modify-playback-state,streaming'
        try:
            client_credentials_manager = SpotifyOAuth(open_browser=False, redirect_uri=SPOTIFY_REDIRECT_URI,
                                                      client_id=SPOTIFY_CLIENT_ID,
                                                      client_secret=SPOTIFY_CLIENT_SECRET,
                                                      scope=self.scope)
            self.spotify = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
            #print('no error')
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

        #print(f'best match={best_match}. uri={best_match_uri}')
        return best_match, best_match_uri

    def play(self, request_dict):
        user_input = request_dict.get('user_input')
        band = request_dict.get('band')
        chunk = request_dict.get('chunk')
        song = request_dict.get('song')

        #print(f'song: {song} band: {band}!')

        if not band:
            # Band is not recognised, search for the song on Spotify
            self._search_and_play(chunk[-1], 'artists')
        else:
            # Band is recognised
            match_band, match_band_uri = self.fuzzy_search_by_name(band, 'artists')
            #print(match_band)

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
                #print(f"Attempting to start playback with URI: {uri}")
                if category == 'tracks':
                    # uris should be a list of track URIs
                    self.spotify.start_playback(uris=[uri])
                else:
                    self.spotify.start_playback(context_uri=uri)
                return True
            except Exception as e:
                #print(f"Error starting playback: {str(e)}")
                return False

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
    def __init__(self):
        self.duration = None
        self.action = self.default_action
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
        filename = '/home/o/resources/alarm1.wav'
        with open(filename, 'rb') as i:
            alarm = i.read()
            send_mqtt_message('vits/alarm', alarm)
            #print('timer expired.')

    def start(self, duration_str):
        self.duration = self.parse_duration(duration_str)
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

    def manage_timer(self, words):
        action = words.get('action')
        if action:
            action = action.lower()
            if action == 'set':
                duration = words.get('duration')
                if duration:
                    self.start(duration.lower())
                    return f"""<|im_start|> system\n
                                    You are Eddie, a friendly, enthusiastic assistant. the user has asked for a timer to be set. the system has successfully set up the timer\n
                                    <|im_end|>\n
                                    <|im_start|>user\n
                                    has a timer been set up?\n
                                    <|im_end|>\n
                                    <|im_start|>Eddie"""
                else:
                    self.start(words.get('user_input'))
                    pass
            elif action == 'cancel':
                self.cancel()
                return f"""<|im_start|> system\n
                                You are Eddie, a friendly, enthusiastic assistant. the user has asked to cancel the timer. the system has successfully cancelled the timer\n
                                <|im_end|>\n
                                <|im_start|>user\n
                                tell me if my timer has been cancelled\n
                                <|im_end|>\n
                                <|im_start|>assistant"""

        query = words.get('query')
        if query:
            return f"""<|im_start|> system\n
                            You are Eddie, a friendly, enthusiastic assistant. there is {round(self.time_left()/60, 2)} minutes left on the timer. this should be relayed when asked\n
                            <|im_end|>\n
                            <|im_start|>user\n
                            how long left on the timer?\n
                            <|im_end|>\n
                            <|im_start|>assistant"""


class weather_manager:
    def __init__(self):
        self.locations = {
            'home': {'lat': 51.751, 'lon': -2.139},
            'cheltenham': {'lat': 51.898, 'lon': -2.075},
            'york': {'lat': 53.958, 'lon': -1.083},
            'mojacar': {'lat': 37.121, 'lon': -1.855},
            'sheffield': {'lat': 53.417, 'lon': -1.500},
            'port talbot': {'lat': 51.592, 'lon': -3.780}}

        self.uk_time = timezone('Europe/London')
        self.owm = pyowm.OWM(OPENWEATHER_API_KEY)
        self.mgr = self.owm.weather_manager()

    def _simple_rule_parse(self, text):
        now = datetime.now(tzlocal()).replace(hour=0,minute=0,second=0)
        dates = {'today': timedelta(days=0),
                 'this': timedelta(days=0),
                 'tomorrow': timedelta(days=1),
                 'week': timedelta(days=7)}
        times = {
            'afternoon': [timedelta(hours=12), timedelta(hours=17, minutes=59, seconds=59)],
            'morning': [timedelta(hours=6), timedelta(hours=11, minutes=59, seconds=59)],
            'evening': [timedelta(hours=18), timedelta(hours=21, minutes=59, seconds=59)],
            'night': [timedelta(hours=22), timedelta(hours=5, minutes=0, seconds=0)],
            'tonight': [timedelta(hours=22), timedelta(hours=5, minutes=0, seconds=0)]}

        date_adjusted = False
        time_adjusted = False

        # Adjust the date and reset time to midnight
        for date_key, date_val in dates.items():
            if date_key in text:
                now = (now + date_val).replace(hour=0, minute=0, second=0, microsecond=0)
                date_adjusted = True

        start_time = now
        end_time = now

        # Adjust for specific times of day
        for time_key, time_vals in times.items():
            if time_key in text:
                start_time += time_vals[0]
                end_time += time_vals[1]
                time_adjusted = True

                if end_time < start_time:
                    end_time += timedelta(days=1)

                break

        # If only a date keyword was found without a specific time, set the end_time to end of that day
        if date_adjusted and not time_adjusted:
            end_time = end_time.replace(hour=23, minute=59, second=59, microsecond=999999)

        #print(datetime.strftime(start_time, '%d/%m/%y %H:%M:%S'))
        #print(datetime.strftime(end_time, '%d/%m/%y %H:%M:%S'))

        return start_time, end_time

    def _location_parser(self, text):
        words = text.split()
        for i in self.locations:
            if i in words:
                return i
        else:
            return 'home'

    def get_weather_type(self, desc):
        if 'thunder' in desc:
            return 'stormy'
        if 'snow' in desc:
            return 'snowy'
        if 'clear' in desc:
            return 'clear'
        if 'drizzle' in desc:
            return 'drizzly'
        if 'cloud' in desc:
            return 'cloudy'
        elif 'rain' in desc:
            return 'rainy'
        else:
            return desc

    def _humidity(self, forecast):
        low = float('inf')
        high = -float('inf')
        for hour in forecast:
            if hour['humidity'] < low:
                low = hour['humidity']
            if hour['humidity'] > high:
                high = hour['humidity']
                return low, high

    def _temps(self, forecast):
        low = float('inf')
        high = -float('inf')
        for hour in forecast:
            if hour['temperature'] < low:
                low = hour['temperature']
            if hour['temperature'] > high:
                high = hour['temperature']
        diff = round(high-low,2)
        return low, high

    def weather_man(self, query):

        user_input = query.get('user_input')
        lingua_franca.load_language('en')
        location = query.get('place')
        date = query.get('date')
        zeit = query.get('duration')

        if not location:
            location = self._location_parser(user_input)

        start_hour, end_hour = self._simple_rule_parse(user_input)

        weather = self.get_forecast(location=location, start_hour=start_hour, end_hour=end_hour)

        grouped_forecast = []
        current_group = None

        for i in range(len(weather)):
            hour = weather[i]

            if i == 0 or hour['weather'] != previous_hour['weather']:
                if current_group:
                    # Calculate average rain percent
                    total_rain_percent = sum(current_group['rain_percent'])
                    average_rain_percent = total_rain_percent / len(current_group['rain_percent'])
                    current_group['average_rain_percent'] = average_rain_percent

                    # Update high temperature
                    current_group['high'] = max(current_group['temps'])

                    grouped_forecast.append(current_group)

                # Create a new group
                current_group = {
                    'first_hour': hour['human_time'],
                    'weather': hour['weather'],
                    'temps': [hour['temperature']],
                    'rain_percent': [hour['rain_percent']],
                    'end_hour': datetime.strptime(hour['human_time'], '%d/%m/%y %H:%M') + timedelta(hours=1)
                }
            else:
                # Add temperature and rain percent to the current group
                current_group['temps'].append(hour['temperature'])
                current_group['rain_percent'].append(hour['rain_percent'])

                # Update end hour if needed
                hour_end = datetime.strptime(hour['human_time'], '%d/%m/%y %H:%M') + timedelta(hours=1)
                if hour_end > current_group['end_hour']:
                    current_group['end_hour'] = hour_end

            previous_hour = hour

        # Handle the last group
        if current_group:
            total_rain_percent = sum(current_group['rain_percent'])
            average_rain_percent = total_rain_percent / len(current_group['rain_percent'])
            current_group['average_rain_percent'] = average_rain_percent
            current_group['high'] = max(current_group['temps'])
            grouped_forecast.append(current_group)

        # Print forecasts
        for group in grouped_forecast:
            return f"""<|im_start|> system\n
                        when asked, create a concise and informative weather forecast using this weather data: from {group['first_hour']} to {group['end_hour'].strftime('%d/%m/%y %H:%M')} it'll be {group['weather']} with a high of {group['high']} degrees and a {round(group['average_rain_percent'])} percent chance of rain\n
                        <|im_end|>\n
                        <|im_start|>user\n
                        "{user_input}"\n
                        <|im_end|>\n
                        <|im_start|>assistant"""

    def get_forecast(self, location='home',start_hour=None, end_hour=None):
        lat = self.locations[location]['lat']
        lon = self.locations[location]['lon']

        if start_hour == end_hour:
            start_hour = datetime.now(tzlocal())
            end_hour = (start_hour + timedelta(hours=1))

        one_call = self.mgr.one_call(lat, lon, units='metric', timezone=self.uk_time)

        hourly_list_full = [weather.to_dict() for weather in one_call.forecast_hourly]
        if not start_hour:
            start_hour = datetime.now(tzlocal())
        if not end_hour:
            end_hour = start_hour+ timedelta(hours=4)
        #print(hourly_list_full)
        hourly_filtered = [hour for hour in hourly_list_full if start_hour.timestamp() <= hour['reference_time'] <= end_hour.timestamp()]

        hourly_list = []
        for hour_dict in hourly_filtered:
            _hour_rain = hour_dict['precipitation_probability']
            hour_rain_percent = int(_hour_rain * 100)
            if hour_rain_percent > 50:
                raining = 'yes'
            else:
                raining = 'no'

            new_dict = {
                #"reference_time": hour_dict["reference_time"],
                "human_time": datetime.strftime(datetime.fromtimestamp(hour_dict["reference_time"]), '%d/%m/%y %H:%M'),
                "status": hour_dict['status'],
                "weather": hour_dict['detailed_status'],
                "temperature": hour_dict["temperature"]["temp"],
                "windspeed": hour_dict['wind']['speed'],
                "cloud_cover": hour_dict['clouds'],
                "rain_percent": hour_rain_percent,
                "raining": raining,
                "humidity": hour_dict["humidity"],
                # Add any other fields you want to include
            }
            hourly_list.append(new_dict)


        return hourly_list

class wikipedia_manager():

    def search(self, query):
        print(query)
        object = query.get('object')
        print(object)
        ans = wikipedia.summary(object, auto_suggest=False)
        sentences = ans.split('.')
        short_summary = sentences[0:3]
        long_summary = sentences[4:]
        return f"{short_summary}|{long_summary}"
