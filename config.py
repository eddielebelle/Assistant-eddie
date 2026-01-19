"""
Configuration file for Eddie Assistant
Load environment variables for credentials and settings
"""
import os
from dotenv import load_dotenv

load_dotenv()

# MQTT Configuration
MQTT_HOST = os.getenv('MQTT_HOST', '192.168.1.57')
MQTT_PORT = int(os.getenv('MQTT_PORT', '1883'))
MQTT_USERNAME = os.getenv('MQTT_USERNAME', 'your_username')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD', 'your_password')

# Spotify Configuration
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID', '')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET', '')
SPOTIFY_REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI', 'http://localhost:8000')

# OpenWeatherMap Configuration
OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY', '')

# Model Paths
WHISPER_MODEL_PATH = os.getenv('WHISPER_MODEL_PATH', '/path/to/whisper/model')
T5_MODEL_PATH = os.getenv('T5_MODEL_PATH', '/path/to/t5/model')
T5_TOKENIZER_PATH = os.getenv('T5_TOKENIZER_PATH', '/path/to/t5/tokenizer')
SPACY_MODEL_PATH = os.getenv('SPACY_MODEL_PATH', '/path/to/spacy/model')

# Resource Paths
SPOTIFY_DATA_PATH = os.getenv('SPOTIFY_DATA_PATH', './resources/spotify_data.json')
ALARM_SOUND_PATH = os.getenv('ALARM_SOUND_PATH', './resources/alarm1.wav')
