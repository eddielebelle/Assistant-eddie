import sys
sys.path.append('..')
from config import MQTT_HOST, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD

import paho.mqtt.client as mqtt


class MQTTMessages:
    def __init__(self, client_id='switch', mqtt_host=None, mqtt_port=None, mqtt_username=None, mqtt_password=None):
        self.mqtt_host = mqtt_host or MQTT_HOST
        self.mqtt_port = mqtt_port or MQTT_PORT
        mqtt_username = mqtt_username or MQTT_USERNAME
        mqtt_password = mqtt_password or MQTT_PASSWORD
        self.client_id = client_id
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.username_pw_set(mqtt_username, mqtt_password)
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.on_publish = self.on_publish

        self.output = None
        self.active = False

    def on_connect(self, client, userdata, flags, rc):
        if rc==0:
            print('switch connected')
            self.mqtt_client.subscribe('flan/translate')

    def on_message(self, client, userdata, message):
        data = message.payload.decode()
        print(data)
        self.active = True
        if message.topic == 'flan/translate':
            self.output = data

    def process_message(self):
        while self.active:
            if self.output:
                print(self.output)
                self.publish_message('server/text', self.output)
                self.publish_message('sys/reset', '')
                self.active = False

    def on_publish(self, client, userdata, mid):
        pass

    def publish_message(self, topic, message):
        self.mqtt_client.publish(topic, message)

    def run(self):
        self.mqtt_client.connect(host=self.mqtt_host, port=self.mqtt_port)
        self.mqtt_client.loop_start()
        print('switchboard online')
        self.process_message()
