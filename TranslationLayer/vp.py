import sys
sys.path.append('..')
from config import MQTT_HOST, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD

import whisper
import threading
import io
import speech_recognition as sr
import whisper
import paho.mqtt.client as mqtt
from datetime import datetime
from tempfile import NamedTemporaryFile
from time import sleep
from queue import Queue, LifoQueue

class voice_processing:
    def __init__(self, client_id='ears', mqtt_host=None, mqtt_port=None, mqtt_username=None, mqtt_password=None):
        mqtt_host = mqtt_host or MQTT_HOST
        mqtt_port = mqtt_port or MQTT_PORT
        mqtt_username = mqtt_username or MQTT_USERNAME
        mqtt_password = mqtt_password or MQTT_PASSWORD
        self.mqtt_client = mqtt.Client(client_id)
        self.mqtt_client.username_pw_set(mqtt_username, mqtt_password)
        self.mqtt_client.connect(mqtt_host, port=mqtt_port)
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.subscribe('mic/pi')
        self.mqtt_client.subscribe('mic/voice')
        self.mqtt_client.subscribe('control/whisper')

        self.rcvd = Queue()
        self.last_sample = bytearray()
        self.phrase_time = LifoQueue()
        self.listening = False
        self.permitted = True
        self.voiced = 0
        self.temp_file = NamedTemporaryFile().name
        self.transcription = ['']

        self.record_timeout = 2
        self.phrase_timeout = 3
        self.voice_probability = 0
        self.voice_cache = 0

        self.model = '/home/o/STT/eddie/whisper_models/small.pt'
        self.audio_model = whisper.load_model(self.model)

    def on_message(self, client, userdata, message):
        data = message.payload
        if message.topic == 'mic/pi':
            self.rcvd.put(data)
            self.phrase_time.put(datetime.utcnow())
        if message.topic == 'mic/voice':
            self.voice_probability = float(message.payload.decode())

    def is_voice(self):
        if self.listening:
            if 0 < self.voice_probability <= 50:
                self.voice_cache += 1
            elif self.voice_probability > 50:
                self.voice_cache = 0
                self.voiced = 1
            if self.voice_cache >= 15:
                self.mqtt_client.publish('mic/control','stop')
                self.voiced = -1
        else:
            self.voiced = 0

    def transcribe(self, audio_data):
        wav_data = io.BytesIO(audio_data.get_wav_data())
        with open(self.temp_file, 'wb') as f:
            f.write(wav_data.read())
        self.rcvd = Queue()
        result = self.audio_model.transcribe(self.temp_file)
        text = result['text'].strip()
        self.mqtt_client.publish('server/text', text)
        self.mqtt_client.publish('input/topic', text)
        print(text)

    def reset(self):
        self.rcvd = Queue()
        self.phrase_time = LifoQueue()
        self.last_sample = bytearray()
        self.transcription = ['']
        self.listening = False
        self.voiced = 0
        self.voice_cache = 0

    def run(self):
        self.mqtt_client.loop_start()
        print('Whisper online')


        while True:
            if not self.rcvd.empty() and self.permitted:
                print('listening')
                self.listening = True

            while self.listening:
                data = self.rcvd.get()
                self.last_sample.extend(data)
                self.is_voice()
                if self.voiced == -1:
                    audio_data = sr.AudioData(bytes(self.last_sample), 16000, 2)
                    self.reset()
                    self.transcribe(audio_data=audio_data)





if __name__ == '__main__':
    voice_recorder = voice_processing()
    voice_recorder.run()
