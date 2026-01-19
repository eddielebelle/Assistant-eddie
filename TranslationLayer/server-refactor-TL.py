import sys
sys.path.append('..')
from config import MQTT_HOST, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD

import io
import speech_recognition as sr
import whisper
import paho.mqtt.client as mqtt
from datetime import datetime
from tempfile import NamedTemporaryFile
from time import sleep
from queue import Queue, LifoQueue
from transformers import AutoTokenizer, pipeline, AutoModelForSeq2SeqLM
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain.llms import HuggingFacePipeline
from prompts import categoriser, kws
import threading

class Translationlayer:
    def __init__(self, mqtt_host, mqtt_port, mqtt_username, mqtt_password, mqtt_topic):
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.username_pw_set(mqtt_username, mqtt_password)
        self.mqtt_client.connect(mqtt_host, port=mqtt_port)
        self.mqtt_client.subscribe(mqtt_topic)
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.on_publish = self.on_publish

        self.rcvd = Queue()
        self.last_sample = bytes()
        self.phrase_time = LifoQueue()
        self.listening = False
        self.voiced = 0
        self.temp_file = NamedTemporaryFile().name
        self.transcription = ['']

        self.record_timeout = 2
        self.phrase_timeout = 3
        self.voice_probability = 0
        self.voice_cache = 0

        #self.tokenizer = AutoTokenizer.from_pretrained('MBZUAI/LaMini-Flan-T5-783M')
        #self.llm = AutoModelForSeq2SeqLM.from_pretrained('MBZUAI/LaMini-Flan-T5-783M', device_map='auto')
        #self.pipe = pipeline("text2text-generation", model=self.llm, tokenizer=self.tokenizer,
        #                     max_length=512, temperature=0.2,)
        #self.flan = HuggingFacePipeline(pipeline=self.pipe)

        self.model = '/Users/owainmogford/Downloads/base.en.pt'
        self.audio_model = whisper.load_model(self.model)
        self.text = ''

    def on_message(self, client, userdata, message):
        #print('received')
        data = message.payload
        if message.topic == 'mic/pi':
            self.rcvd.put(data)
            self.phrase_time.put(datetime.utcnow())
        if message.topic == 'mic/voice':
            self.voice_probability = float(message.payload.decode())

    def on_publish(self, client, userdata, message):
        msg = message.payload
        with open('/Users/owainmogford/Desktop/log.txt', 'a') as f:
            f.write(f'{datetime.now("GB")}: {msg}')

    def is_voice(self):
        #print(self.voiced)
        if self.listening:
            if 0 < self.voice_probability <= 50:
                self.voice_cache += 1
            elif self.voice_probability > 50:
                self.voice_cache = 0
                self.voiced = 1
            if self.voice_cache >= 15:
                self.voiced = -1
        else:
            self.voiced = 0

    def transcribe(self, audio_data):
        wav_data = io.BytesIO(audio_data.get_wav_data())
        with open(self.temp_file, 'w+b') as f:
            f.write(wav_data.read())
        self.rcvd = Queue()
        result = self.audio_model.transcribe(self.temp_file)
        self.text = result['text'].strip()
        self.mqtt_client.publish('server/text', self.text)
        print(self.text)
        self.reset()
        #return text

    def category(self, sentence):
        cats = PromptTemplate(template=categoriser, input_varibles=["sentence"])
        catchain = LLMChain(llm=self.flan, prompt=cats)
        catparse = catchain.run(sentence)
        print(catparse)
        return catparse

    def keyword(self, sentence):
        key = PromptTemplate(template=kws, input_varibles=["sentence"])
        keychain = LLMChain(llm=self.flan, prompt=key)
        keyparse = keychain.run(sentence)
        print(keyparse)
        return keyparse

    def reset(self):
        self.rcvd = Queue()
        self.phrase_time = LifoQueue()
        self.last_sample = bytes()
        self.transcription = ['']
        self.listening = False
        self.voiced = 0

    def run(self):
        print('ready')
        self.mqtt_client.loop_start()

        while True:
            #print(self.rcvd.qsize())
            if not self.listening:
                sleep(1)
            if not self.rcvd.empty():
                print('listening')
                self.listening = True

            while self.listening:
                data = self.rcvd.get()
                self.last_sample += data
                self.is_voice()
                if self.voiced == -1:
                    self.transcribe(audio_data = sr.AudioData(self.last_sample,16000,2))
                    self.keyword(self.text)
                    self.category(self.text)
                    self.reset()


if __name__ == '__main__':
    voice_recorder = Translationlayer(
    mqtt_host=MQTT_HOST,
    mqtt_port=MQTT_PORT,
    mqtt_username=MQTT_USERNAME,
    mqtt_password=MQTT_PASSWORD,
    mqtt_topic=[('mic/pi',0),('mic/voice',0)])

    voice_recorder.run()
