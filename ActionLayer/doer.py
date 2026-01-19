import paho.mqtt.client as mqtt
from queue import Queue
import threading
import en_core_web_sm
from categories import categories
import json
from tools import clock_manager, music_manager, CustomTimer, dice_manager, weather_manager
import traceback
import time
import sys
import sdnotify
from statemachine import StateMachine, State
from config import MQTT_HOST, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD

class PolyStateMachine(StateMachine):
    inactive = State('inactive', initial=True)
    working = State('working')
    waiting = State('waiting')

    start_working = inactive.to(working)
    stop_working = working.to(inactive)

    start_waiting = working.to(waiting)
    stop_waiting = waiting.to(inactive)

    in_waiting = inactive.to(waiting)

    def on_start_working(self):
        pass

    def on_stop_working(self):
        pass

    def on_start_waiting(self):
        pass

    def on_stop_waiting(self):
        pass

    def on_in_waiting(self):
        pass

class polyglot:
    def __init__(self, client_id='backend', mqtt_host=None, mqtt_port=None, mqtt_username=None, mqtt_password=None):
        self.client_id = client_id
        mqtt_host = mqtt_host or MQTT_HOST
        mqtt_port = mqtt_port or MQTT_PORT
        mqtt_username = mqtt_username or MQTT_USERNAME
        mqtt_password = mqtt_password or MQTT_PASSWORD

        self.mqtt_client = mqtt.Client()
        self.mqtt_client.username_pw_set(mqtt_username, mqtt_password)
        self.mqtt_client.connect(mqtt_host, port=mqtt_port)
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.loop_start()
        self.client_source = None

        self.can_proceed = 0
        self.request = None
        self.rcvd = Queue()
        self.category = None
        self.keywords = None

        self.sensor_data = {}
        self.process_states = {}
        self.last_heartbeat_time = time.time()

        self.CustomTimer = CustomTimer()
        self.music_manager = music_manager()
        self.weather_manager = weather_manager()

        self.active = False
        self.tools = {
            'clock': clock_manager,
            'timer': self.CustomTimer.manage_timer,
            'music': self.music_manager.manage_music,
            'dice roll': dice_manager,
            'weather': self.weather_manager.weather_man,
        }

        PolyStateMachine.on_start_working = self.on_start_working
        PolyStateMachine.on_stop_working = self.on_stop_working
        PolyStateMachine.on_start_waiting = self.on_start_waiting
        PolyStateMachine.on_stop_waiting = self.on_stop_working
        PolyStateMachine.on_in_waiting = self.on_in_waiting

        self.state_machine = PolyStateMachine()

    def on_start_working(self):
        self.mqtt_client.publish('poly/state', 'working')

    def on_stop_working(self):
        self.mqtt_client.publish('poly/state', 'inactive')
        self.active = False

    def on_start_waiting(self):
        self.mqtt_client.publish('poly/state', 'waiting')

    def on_stop_waiting(self):
        self.mqtt_client.publish('poly/state', 'inactive')

    def on_in_waiting(self):
        self.mqtt_client.publish('poly/state', 'waiting')

    def on_permission_granted(self):
        self.mqtt_client.publish('poly/state', 'proceeding')

    def on_connect(self, client, userdata, flags, rc):
        if rc==0:
            #print('switch connected')
            self.mqtt_client.subscribe('convo/reply')
            self.mqtt_client.subscribe('step-one/action')
            self.mqtt_client.subscribe('sensor/#')
            self.mqtt_client.subscribe('process/#')

    def heartbeat(self):
        heartbeat_interval = 30
        last_heartbeat_time = self.last_heartbeat_time
        current_time = time.time()
        if current_time - last_heartbeat_time >= heartbeat_interval:
            sdnotify.SystemdNotifier().notify('WATCHDOG=1')
            self.last_heartbeat_time = current_time

    def on_message(self, client, userdata, message):
        data = message.payload.decode()
        print(f'incoming data={data}')
        self.active = True
        if message.topic == 'step-one/action':
            self.rcvd.put(data)

    def process_text(self):
        while not self.active:
            self.heartbeat()
            time.sleep(0.1)
            if not self.rcvd.empty():
                self.state_machine.start_working()
                data = self.rcvd.get()
                self.rcvd = Queue()
                try:
                    self.client_source = data.split('~')[1]
                    data = data.split('~')[0]
                except IndexError:
                    print(f'error {message.topic} > {data}')
                print(f'this is just before data split {data}')
                category, keywords_str = data.split('|')
                category = category.strip()
                self.category = category
                self.keywords = json.loads(keywords_str.strip())
                self.take_action()

    def execute_tool(self, category, keywords):
        try:
            tool = self.tools[category]
            print(f"execute 1")
            #self.mqtt_client.publish('tool/current', f'{category}|{self.client_source}')
            result = tool(keywords)
            print(f'execute 2')
            return result
        except Exception as e:
            print(f"Error executing tool '{category}': {str(e)}")
            traceback.print_exc()
            return None

    def take_action(self):
        if self.category in self.tools:
                task = self.execute_tool(self.category, self.keywords)
                if task is not None:
                    self.mqtt_client.publish('step-one/tool', f'{task}~{self.client_source}')
                else:
                    if self.client_source == 'mic/mbp':
                        self.mqtt_client.publish('vits/mbp', f"Error executing tool '{self.category}'")
                    if self.client_source == 'mic/pi':
                        self.mqtt_client.publish('vits/pi', f"Error executing tool '{self.category}'")

        else:
            if self.client_source == 'mic/mbp':
                self.mqtt_client.publish('vits/mbp', f"I'm sorry I cant help, the category {self.category} isnt set up")
            if self.client_source == 'mic/pi':
                self.mqtt_client.publish('vits/pi', f"I'm sorry I cant help, the category {self.category} isnt set up")
        self.state_machine.stop_working()

    def run(self):
        sdnotify.SystemdNotifier().notify('READY=1')
        while True:
                self.process_text()

p = polyglot()
p.run()

