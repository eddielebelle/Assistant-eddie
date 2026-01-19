import sys
sys.path.append('..')
from config import MQTT_HOST, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD

import paho.mqtt.client as mqtt
import os
import datetime
from TTS.api import TTS
import time
import threading
import torch
import sdnotify

class voicer:
    def __init__(self, client_id='mouth', mqtt_host=None, mqtt_port=None, mqtt_username=None, mqtt_password=None):
        mqtt_host = mqtt_host or MQTT_HOST
        mqtt_port = mqtt_port or MQTT_PORT
        mqtt_username = mqtt_username or MQTT_USERNAME
        mqtt_password = mqtt_password or MQTT_PASSWORD
        self.client_id = client_id
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.username_pw_set(mqtt_username, mqtt_password)
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.connect(mqtt_host, port=mqtt_port)
        self.mqtt_client.subscribe('vits/in')
        self.mqtt_client.loop_start()
        self.client_source = None
        self.device = 'cuda'
        self.voice = TTS(model_name="tts_models/en/vctk/vits", progress_bar=False).to(self.device)
        self.last_heartbeat_time = time.time()

    def on_message(self, client, userdata, message):
        print('msg in')
        topic = message.topic
        payload = message.payload.decode()
        try:
            payload, self.client_source = payload.split('~')
        except ValueError:
            print(payload)
        #print(payload)
        if topic == 'vits/in':
            self.process_text(payload)
        else:
            print('BOOING!')

    def process_text(self, words):
        if not isinstance(words, str) or len(words) < 2:
            words = 'my brain forgot to tell me what to say'
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"/home/o/Eddie/recordings/{timestamp}.wav"
        print(words)
        wav = self.voice.tts_to_file(text=words, speaker=self.voice.speakers[80], file_path=filename)
        with open(filename, 'rb') as file:
            wav_data = file.read()
            if self.client_source == 'mic/mbp':
                self.mqtt_client.publish('vits/mbp', wav_data)
            if self.client_source == 'mic/pi':
                self.mqtt_client.publish('vits/pi', wav_data)
            print('Text processed and sent.')

    def notifier(self):
        heartbeat_interval = 30
        current_time = time.time()
        last_heartbeat_time = self.last_heartbeat_time
        if current_time - last_heartbeat_time >= heartbeat_interval:
            sdnotify.SystemdNotifier().notify('WATCHDOG=1')
            print('WATCHDOG=1')
            self.last_heartbeat_time = current_time

    def run(self):
        print('vits online')
        sdnotify.SystemdNotifier().notify('READY=1')
        print('heart started')
        while True:
            self.notifier()
            time.sleep(0.1)

v = voicer()
v.run()
