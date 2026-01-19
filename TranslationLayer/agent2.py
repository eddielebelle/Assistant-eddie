import sys
sys.path.append('..')
from config import MQTT_HOST, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD

from langchain.chains import TransformChain, LLMChain, SimpleSequentialChain
from langchain.prompts import PromptTemplate
import concurrent.futures
from langchain.llms import HuggingFacePipeline
import threading
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline, AutoModelForSeq2SeqLM
from TranslationLayer.prompts import kws, categoriser, clock
import paho.mqtt.client as mqtt
import re
from time import sleep

class flan:
    def __init__(self, client_id='brain', mqtt_host=None, mqtt_port=None, mqtt_username=None, mqtt_password=None):
        mqtt_host = mqtt_host or MQTT_HOST
        mqtt_port = mqtt_port or MQTT_PORT
        mqtt_username = mqtt_username or MQTT_USERNAME
        mqtt_password = mqtt_password or MQTT_PASSWORD
        self.mqtt_client = mqtt.Client(client_id)
        self.mqtt_client.username_pw_set(mqtt_username, mqtt_password)
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.on_publish  = self.on_publish
        self.mqtt_client.connect(mqtt_host, port=mqtt_port)
        self.mqtt_client.subscribe('input/topic')
        self.mqtt_client.subscribe('clock/flan')

        self.device = torch.device(0)
        self.tokenizer = AutoTokenizer.from_pretrained('MBZUAI/LaMini-Flan-T5-783M')
        self.model = AutoModelForSeq2SeqLM.from_pretrained('MBZUAI/LaMini-Flan-T5-783M').to(self.device)
        self.pipe = pipeline("text2text-generation", model=self.model, tokenizer=self.tokenizer, device=self.device, max_length=512, temperature=0.2)
        self.llm = HuggingFacePipeline(pipeline=self.pipe)

        self.keyprompt = PromptTemplate(template=kws, input_variables=['sentence'])
        self.catprompt = PromptTemplate(template=categoriser, input_variables=['sentence'])
        self.timeprompt = PromptTemplate(template=clock, input_variables=['sentence'])

        self.dick = LLMChain(llm=self.llm, prompt=self.keyprompt)
        self.chainy = LLMChain(llm=self.llm, prompt=self.catprompt)
        self.clocky = LLMChain(llm=self.llm, prompt=self.timeprompt)

        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

        self.keywords = None
        self.category = None
        self.thinking = False

    def keyfind(self, query):
        chain = self.dick.run(query)
        post = chain.replace('.','').lower()
        return post

    def typer(self, query):
        chain = self.chainy.run(query)
        post = re.sub(r'[^\w\s]', '', chain)
        post = post.split()
        end = post[-1].lower()
        return end

    def keyfind_callback(self, result):
        print('keyfind callback')
        self.keywords = result

    def typer_callback(self, result):
        print('typer callback')
        self.category = result

    def submit_threads(self, data):
        future1 = self.executor.submit(self.keyfind, data)
        future2 = self.executor.submit(self.typer, data)

        future1.add_done_callback(lambda f: self.keyfind_callback(f.result()))
        future2.add_done_callback(lambda f: self.typer_callback(f.result()))

    def on_message(self, client, userdata, message):
        data = message.payload
        if message.topic == 'input/topic':
            if self.thinking:
                return
            else:
                self.submit_threads(data)
                self.thinking = True
        else:
            print(f'something went wrong...{message.topic}->{data}')

    def run(self):
        self.mqtt_client.loop_start()
        print('Agent online')

        while True:
            if self.keywords and self.category:
                print('publishing work')
                self.mqtt_client.publish('flan/out', f'{self.category}/{self.keywords}')
                self.keywords = None
                self.category = None
                self.thinking = False



