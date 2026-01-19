import sys
sys.path.append('..')
from config import MQTT_HOST, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD

from queue import Queue, LifoQueue
from llama_cpp import Llama
#import torch
#from TranslationLayer.prompts import kws, categoriser, clock
import socket
from ActionLayer.categories import categories
import re
import threading
import io
import speech_recognition as sr
import whisper
import paho.mqtt.client as mqtt
from datetime import datetime
from tempfile import NamedTemporaryFile
import time
import spacy
import json
import sdnotify

class translator:
    def __init__(self, client_id='interface', mqtt_host=None, mqtt_port=None, mqtt_username=None,
                 mqtt_password=None):
        mqtt_host = mqtt_host or MQTT_HOST
        mqtt_port = mqtt_port or MQTT_PORT
        mqtt_username = mqtt_username or MQTT_USERNAME
        mqtt_password = mqtt_password or MQTT_PASSWORD
        self.mqtt_client = mqtt.Client(client_id)
        self.mqtt_client.username_pw_set(mqtt_username, mqtt_password)
        self.mqtt_client.connect(mqtt_host, port=mqtt_port)
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.subscribe('mic/mbp')
        self.mqtt_client.subscribe('mic/pi')
        self.mqtt_client.subscribe('mic/voice')
        self.mqtt_client.subscribe('input/topic')
        self.mqtt_client.subscribe('flan/in')
        self.mqtt_client.subscribe('internal/confirm')
        self.client_source = None

        self.rcvd = Queue()
        self.last_sample = bytearray()
        self.phrase_time = LifoQueue()
        self.listening = False

        self.keyqueue = Queue()
        self.catqueue = Queue()

        self.keywords = None
        self.category = None
        self.words = None
        self.flan_input = None

        self.voiced = 0
        self.convo_state = 'listening'

        self.temp_file = NamedTemporaryFile().name
        self.transcription = ['']

        self.record_timeout = 2
        self.phrase_timeout = 3
        self.voice_probability = 0
        self.voice_cache = 0
        # initialising whisper
        self.model = '/home/o/STT/eddie/whisper_models/small.en.pt'
        self.audio_model = whisper.load_model(self.model)
        # initialising LLM
        self.n_gpu_layers = 64  # Change this value based on your model and your GPU VRAM pool.
        self.n_batch = 4096

        self.llm = Llama(
            model_path="/home/o/quant/mistral-7b-openorca.Q4_K_M.gguf",
            n_gpu_layers=self.n_gpu_layers,
            n_batch=self.n_batch,
        )
        # initialising spacy
        self.nlpC = spacy.load("en_core_web_lg")
        self.nlpB = spacy.load("/home/o/resources/en_core_web_lg_ner1")
        self.nlpS = spacy.load("/home/o/resources/en_core_web_lg_nerS")

    def keyfind(self, keywords):
        keydict = {}
        keydict['user_input'] = self.words
        keydict['chunk'] = []
        action_assigned = False
        tag_set = {'WRB', 'WP', 'WDT'}
        label_mapping = {
            'TIME': 'duration',
            'DATE': 'date',
            'GPE': 'place',
            'QUANTITY': 'amount',
            'EVENT': 'event',
            'PERSON': 'person',
            'BAND': 'band',
            'SONG': 'song',
        }

        kwC = self.nlpC(keywords)
        kw = self.nlpB(keywords)
        kwS = self.nlpS(keywords)

        for token in kw:
            if token.pos_ == 'VERB' and not action_assigned:
                print(f'lemma={token.lemma_}')
                keydict['action'] = token.text
                action_assigned = True
            if token.tag_ in tag_set:
                keydict['query'] = token.text

        for ent in kw.ents:
            print(f"K: {ent.text, ent.label_}")
            if ent.label_ in label_mapping and ent.label_ != 'SONG':
                keydict[label_mapping[ent.label_]] = ent.text

        for ent in kwC.ents:
            print(f"C: {ent.text, ent.label_}")
            if ent.label_ in label_mapping:
                keydict[label_mapping[ent.label_]] = ent.text

        for ent in kwS.ents:
            print(f"S: {ent.text, ent.label_}")
            if ent.label_ == 'SONG':
                keydict['song'] = ent.text

        for chunk in kw.noun_chunks:
            keydict['chunk'].append(chunk.text)

        print(keydict)
        self.keyqueue.put(keydict)

    def typer(self, query):
        prompt = f"""<|im_start|>system\n
                You are Eddie, a super helpful digital assistant. this is a list of tools you can choose to answer a query:\n
                alarm - this can be used to set up, check or cancel an alarm\n
                cinema - this is used to find information about films or actors\n
                clock - this is used to tell the time anywhere in the world\n
                chat - this is used to have a conversation with the end user\n
                communication - this is used to send messages to others\n
                definition - this can be used to get definitions of words or phrases\n
                dice roll - this can be used to simulate rolling dice\n
                fact find - this is used to search the internet to find facts\n
                heating - this can be used to control the temperature in the house\n
                history - this is used to find historical facts and answer historical questions\n
                keep score - this can be used to keep track of scores in games\n
                lights - this is used to turn lights on or off in rooms in the house\n
                maths - this is used to answer maths queries\n
                meaning - this is used to find the meaning of words\n
                music - this can be used to play music, and control a music player\n
                news - used to get current news and reply to questions about headlines, or current events\n
                notes - useful to take notes from the user\n
                spelling - used to spell out a given word\n
                schedule - this can be used to manage upcoming appointments
                timer - this can be used to set up, check or cancel timers\n
                translate - this can be used to translate between languages\n
                weather - this can be used to answer questions about weather\n
                <|im_end|>\n
                <|im_start|>user\n
                which tool should be used to respond to this sentence: {query}<|im_end|>\n"""

        start = datetime.now()
        output = self.llm(prompt)['choices'][0]['text']
        end = datetime.now()
        print(f'output={output} took-{end-start}')
        matched = [c for c in categories if c in output]

        if matched:
            print(matched)
            category = matched[0]
            print(category)
            self.catqueue.put(category)

    def is_voice(self):
        if self.listening:
            if 0 < self.voice_probability <= 50:
                self.voice_cache += 1
            elif self.voice_probability > 50:
                self.voice_cache = 0
                self.voiced = 1
            if self.voice_cache >= 15:
                self.mqtt_client.publish('mic/control', 'stop')
                self.voiced = -1
        else:
            self.voiced = 0

    def process_audio(self):
        print('ready')
        heartbeat_interval = 30
        last_heartbeat_time = time.time()
        while self.voiced == 0:
            if not self.rcvd.empty():
                print('listening')
                self.listening = True

            while self.listening:
                data = self.rcvd.get()
                self.last_sample.extend(data)
                self.is_voice()
                if self.voiced == -1:
                    audio_data = sr.AudioData(bytes(self.last_sample), 16000, 2)
                    self.audio_reset()
                    self.transcribe(audio_data=audio_data)
                    if self.words and self.convo_state == 'listening':
                        T1 = threading.Thread(target=self.keyfind, args=(self.words,))
                        T1.daemon = True
                        T2 = threading.Thread(target=self.typer, args=(self.words,))
                        T2.daemon = True

                        T1.start()
                        T2.start()

                        T1.join()
                        T2.join()
                        self.keywords = self.keyqueue.get()
                        self.category = self.catqueue.get()
                    if self.words and self.convo_state == 'confirmation':


            if self.keywords and self.category:
                self.mqtt_client.publish('flan/translate', f'{self.client_source}~{self.category}|{json.dumps(self.keywords)}')
                self.llm_reset()

            if self.flan_input:
                self.process_text()
                self.flan_input = None

            current_time = time.time()
            if current_time - last_heartbeat_time >= heartbeat_interval:
                sdnotify.SystemdNotifier().notify('WATCHDOG=1')
                print('WATCHDOG=1')
                last_heartbeat_time = current_time

    def transcribe(self, audio_data):
        wav_data = io.BytesIO(audio_data.get_wav_data())
        with open(self.temp_file, 'wb') as f:
            f.write(wav_data.read())
        self.audio_reset()
        result = self.audio_model.transcribe(self.temp_file)
        text = result['text'].strip()
        self.words = text
        self.mqtt_client.publish('server/text', text)
        self.mqtt_client.publish('input/topic', text)
        print(text)

    def process_text(self):
        input_prompt = f'{self.flan_input}'
        print(f'in-{input_prompt}')
        if '$' in input_prompt:
            flow, prompt = input_prompt.split('$')
            print(flow, prompt)
            output = self.llm(prompt)['choices'][0]['text'].strip()
            channel = f'{flow}/out'
            print(channel)
            print(output)
            try:
                self.mqtt_client.publish(channel, output)
            except TypeError:
                print(f'Error---{output}+{type(output)}')
        else:
            start = datetime.now()
            output = self.llm(input_prompt)['choices'][0]['text']
            end = datetime.now()
            print(output)
            first = output.split('<')[0].strip()
            print(f'{first} took-{end-start}')
            self.mqtt_client.publish('vits/in', f'{first}~{self.client_source}')
            self.client_source = None

    def audio_reset(self):
        self.rcvd = Queue()
        self.phrase_time = LifoQueue()
        self.last_sample = bytearray()
        self.transcription = ['']
        self.listening = False
        self.voice_cache = 0

    def llm_reset(self):
        self.keywords = None
        self.category = None
        self.words = None
        self.voiced = 0

    def on_message(self, client, userdata, message):
        data = message.payload
        if self.convo_state == 'listening':
            if message.topic == 'mic/mbp' or message.topic == 'mic/pi':
                self.client_source = message.topic
                self.rcvd.put(data)
                self.phrase_time.put(datetime.utcnow())
            if message.topic == 'mic/voice':
                self.voice_probability = float(message.payload.decode())
            if message.topic == 'flan/in':
                print('msg received')
                decoded = message.payload.decode('utf-8')
                self.flan_input = decoded
            if message.topic == 'internal/confirm':
                self.convo_state = 'checking'
                self.mqtt_client.publish('check')
        if self.convo_state == 'checking':
            if message.topic == 'mic/mbp' or message.topic == 'mic/pi':
                self.client_source = message.topic
                self.transcribe(audio_data=)#TO-DO - seperate transcription as per quanttest4 and continue mqtt flow to control function
            if message.topic == 'mic/voice':
                self.voice_probability = float(message.payload.decode())

    def run(self):
        sdnotify.SystemdNotifier().notify('READY=1')
        self.mqtt_client.loop_start()
        self.process_audio()
