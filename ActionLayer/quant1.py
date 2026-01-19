import sys
sys.path.append('..')
from config import MQTT_HOST, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD

from langchain.chains import TransformChain, LLMChain
from langchain.prompts import PromptTemplate
from langchain.llms import HuggingFacePipeline
from queue import Queue, LifoQueue
import torch
from ctransformers import AutoModelForCausalLM
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
import spacy
import json

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
        self.mqtt_client.subscribe('mic/mbp')
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
        # initialising whisper
        self.model = '/home/o/STT/eddie/whisper_models/small.en.pt'
        self.audio_model = whisper.load_model(self.model)
        # initialising LLM
        self.device = torch.device(0)
        #self.tokenizer = T5Tokenizer.from_pretrained('/home/o/llm/T5token_L')
        self.model = AutoModelForCausalLM.from_pretrained('/home/o/quant/mistral-7b-openorca.Q4_K_M.gguf')
        self.pipe = pipeline("text2text-generation", model=self.model, device=self.device,
                             max_length=512, temperature=0.2)
        self.llm = HuggingFacePipeline(pipeline=self.pipe)

        self.catprompt = PromptTemplate(template=categoriser, input_variables=['sentence'])
        self.chainy = LLMChain(llm=self.llm, prompt=self.catprompt)
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

        for token in kwS:
            print(f'S: {token.text, token.tag_}')

        for ent in kwS.ents:
            print(f"S: {ent.text, ent.label_}")
            if ent.label_ == 'SONG':
                keydict['song'] = ent.text

        for chunk in kw.noun_chunks:
            keydict['chunk'].append(chunk.text)

        print(keydict)
        self.keyqueue.put(keydict)

    def typer(self, query):
        chain = self.chainy.run(query)
        post = re.sub(r'[^\w\s]', '', chain)
        self.catqueue.put(post)

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
                self.mqtt_client.publish('flan/translate', f'{self.category}|{json.dumps(self.keywords)}')
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
        if '$' in input_prompt:
            flow, prompt = input_prompt.split('$')
            print(flow, prompt)
            output = self.llm(prompt)
            channel = f'{flow}/out'
            print(channel)
            self.mqtt_client.publish(channel, output)
        else:
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
        if message.topic == 'mic/mbp':
            self.rcvd.put(data)
            self.phrase_time.put(datetime.utcnow())
        if message.topic == 'mic/voice':
            self.voice_probability = float(message.payload.decode())
        if message.topic == 'flan/in':
            print('msg received')
            decoded = message.payload.decode('utf-8')
            self.flan_input = decoded

    def run(self):
        self.process_audio()

x = translator()
x.run()
