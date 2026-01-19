import sys
sys.path.append('..')
from config import MQTT_HOST, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD

from langchain.chains import TransformChain, LLMChain, SimpleSequentialChain
from langchain.prompts import PromptTemplate
from langchain.llms import HuggingFacePipeline
from queue import Queue, LifoQueue
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline, AutoModelForSeq2SeqLM
from TranslationLayer.prompts import kws, categoriser, clock
import re
import threading
import io
import speech_recognition as sr
import whisper
import paho.mqtt.client as mqtt
from datetime import datetime
from tempfile import NamedTemporaryFile
from time import sleep


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
        self.mqtt_client.loop_start()
        self.mqtt_client.subscribe('mic/pi')
        self.mqtt_client.subscribe('mic/voice')
        self.mqtt_client.subscribe('input/topic')
        self.mqtt_client.subscribe('flan/in')

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

        self.temp_file = NamedTemporaryFile().name
        self.transcription = ['']

        self.record_timeout = 2
        self.phrase_timeout = 3
        self.voice_probability = 0
        self.voice_cache = 0
        # initializing whisper
        self.model = '/home/o/STT/eddie/whisper_models/small.pt'
        self.audio_model = whisper.load_model(self.model)
        # initializing LLM
        self.device = torch.device(0)
        self.tokenizer = AutoTokenizer.from_pretrained('MBZUAI/LaMini-Flan-T5-783M')
        self.model = AutoModelForSeq2SeqLM.from_pretrained('MBZUAI/LaMini-Flan-T5-783M').to(self.device)
        self.pipe = pipeline("text2text-generation", model=self.model, tokenizer=self.tokenizer, device=self.device,
                             max_length=512, temperature=0.2)
        self.llm = HuggingFacePipeline(pipeline=self.pipe)

        self.keyprompt = PromptTemplate(template=kws, input_variables=['sentence'])
        self.catprompt = PromptTemplate(template=categoriser, input_variables=['sentence'])
        self.timeprompt = PromptTemplate(template=clock, input_variables=['sentence'])

        self.dick = LLMChain(llm=self.llm, prompt=self.keyprompt)
        self.chainy = LLMChain(llm=self.llm, prompt=self.catprompt)
        self.clocky = LLMChain(llm=self.llm, prompt=self.timeprompt)

    def keyfind(self, query):
        chain = self.dick.run(query)
        post = chain.replace('.', '').lower()
        self.keyqueue.put(post)

    def typer(self, query):
        chain = self.chainy.run(query)
        post = re.sub(r'[^\w\s]', '', chain)
        post = post.split()
        end = post[-1].lower()
        self.catqueue.put(end)

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
                    if self.words:
                        T1 = threading.Thread(target=self.keyfind, args=(self.words,))
                        T2 = threading.Thread(target=self.typer, args=(self.words,))

                        T1.start()
                        T2.start()

                        T1.join()
                        T2.join()
                        self.keywords = self.keyqueue.get()
                        self.category = self.catqueue.get()
            if self.keywords and self.category:
                self.mqtt_client.publish('flan/translate', f'{self.category}:{self.keywords}')
                self.llm_reset()

            if self.flan_input:
                self.process_text()
                self.flan_input = None


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
        output = self.llm(input_prompt)
        self.mqtt_client.publish('vits/in', output)

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
        if message.topic == 'mic/pi':
            self.rcvd.put(data)
            self.phrase_time.put(datetime.utcnow())
        if message.topic == 'mic/voice':
            self.voice_probability = float(message.payload.decode())
        if message.topic == 'flan/in':
            print('msg received')
            self.flan_input = data


    def run(self):
        self.process_audio()
