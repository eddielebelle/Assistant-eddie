import paho.mqtt.client as mqtt
from datetime import datetime
import pytz
from timezones import timezones

def clock(self, city='london'):
        zone = timezones[city]
        tz = pytz.timezone(zone)
        now = datetime.now(tz)
        hour = now.strftime('%-I')
        minutes = now.minute
        if minutes == 0:
            time = f'{hour} o clock'
        if minutes == 15:
            time = f'quarter past {hour}'
        if minutes == 30:
            time = f'half past {hour}'
        if minutes == 45:
            time = f'quarter to {hour}'
        if minutes < 30:
            time = f'{minutes} minutes past {hour}'
        if minutes > 30:
            time = f'{60 - minutes} minutes to {hour}'
            return time

