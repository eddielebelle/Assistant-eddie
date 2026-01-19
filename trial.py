import sys
sys.path.append('.')
from config import MQTT_HOST, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD

from TranslationLayer import MQTTswitchboard, translator, vits
#from ActionLayer import clock
import paho.mqtt.client as mqtt

class manager():
    def __init__(self, client_id='bigboss', mqtt_host=None, mqtt_port=None, mqtt_username=None,
                 mqtt_password=None):
        mqtt_host = mqtt_host or MQTT_HOST
        mqtt_port = mqtt_port or MQTT_PORT
        mqtt_username = mqtt_username or MQTT_USERNAME
        mqtt_password = mqtt_password or MQTT_PASSWORD
        self.mqtt_client = mqtt.Client(client_id)
        self.mqtt_client.username_pw_set(mqtt_username, mqtt_password)
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.connect(mqtt_host, port=mqtt_port)
        self.flanslate = None

    def on_message(self, client, userdata, message):
        data = message.payload.decode()
        in_point = message.topic
        print(in_point, data)
        if in_point == 'flan/translate':
            self.flanslate = data
        self.mqtt_client.loop_stop()

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print('switch connected')
            self.mqtt_client.subscribe('flan/translate')

    def run(self):
        while True:
            self.mqtt_client.loop_start()
            translate = translator.translator()
            speak = vits.voicer()
            translate.run()
            speak.run()
            self.mqtt_client.publish('sys/reset' 'start')

#PLAY WITH RETENTION... set local variables

#tool_clock = clock.clock()
m = manager()
m.run()
