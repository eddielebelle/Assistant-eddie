request = input['input']
task = input['action']
action = input['action']
query = input['query']
when = input['date']
where = input['place']
time = input['duration']
who = input['person']


def alarm_manager(self,input):
    #b"alarm|{'input': 'Set an alarm for tomorrow at seven.', 'chunk': {'an alarm', 'tomorrow'}, 'action': 'Set', 'date': 'tomorrow'}"
    if input['action']:
        if input['action'].lower() == 'set':
            if input['duration']:
                alarm.set(input['duration'])
            elif input['date']:
                alarm.set(input['date'])
        elif input['action'].lower() == 'cancel':
            alarm.cancel()
     if input['query']:
         if input['query'].lower() == 'what' or input['query'].lower() == 'when'
            alarm.check()

def calendar_manager(self, input):
    #b'calendar and appointments|{\'input\': "When\'s my next appointment?", \'chunk\': {\'my next appointment\'}, \'query\': \'When\'}'
    #b'calendar and appointments|{\'input\': "Is there a reminder there\'s a module board tomorrow?", \'chunk\': {\'a module board\', \'a reminder\'}, \'action\': "\'s", \'date\': \'tomorrow\'}'

def clock_manager(self, input):
    #b"world clock|{'input': 'What time is it?', 'chunk': {'What time', 'it'}, 'query': 'What'}"
    if input['place']:
        location = input['place'].lower()
        clock(city=location)
    else:
        clock()

def comms_manager():
    #b"communication|{'input': 'Send a message to my mum.', 'chunk': {'a message', 'my mum'}, 'action': 'Send'}"
    pass

def dates_manager():
    #b'date|{\'input\': "What\'s the date today?", \'chunk\': {\'the date\', \'What\'}, \'query\': \'What\', \'date\': \'today\'}'
    pass
def definition_manager():
#meaning too
    #b"definition|{'input': 'What does amtocrative mean?', 'chunk': {'amtocrative', 'What'}, 'query': 'What', 'action': 'mean'}"
    #b"meaning|{'input': 'Why is maybe so cute?', 'chunk': set(), 'query': 'Why'}"
    #b"definition|{'input': 'Why is a sausage so big?', 'chunk': {'a sausage'}, 'query': 'Why'}"
    pass

def dice_manager(self, input):
    #coin toss
    #b"simulate rolling dice|{'input': 'Roll to six sided dice', 'chunk': {'six sided dice', 'Roll'}}"
    #b"simulate rolling dice|{'input': 'Toss a coin please.', 'chunk': {'a coin please'}, 'action': 'Toss'}"
    pass

def search_manager():
#history, fact
    #"history|{'input': 'Use the President of the United States.', 'chunk': {'the United States', 'the President'}, 'action': 'Use', 'place': 'the United States'}"
    pass

def heating_manager():
    #b"control the heating|{'input': 'Turn the heating off in the living room.', 'chunk': {'the living room', 'the heating'}, 'action': 'Turn'}"
    pass

def joke_manager():
    #b"jokes|{'input': 'Tell me a joke about Pokemon.', 'chunk': {'Pokemon', 'me', 'a joke'}, 'action': 'Tell'}"
    pass

def score_manager():
    #b'keep score|{\'input\': "I\'ve won to my school.", \'chunk\': {\'my school\', \'I\'}, \'action\': \'won\'}'
    pass

def light_manager():
    #b"control the lights|{'input': 'change the lights to pink in the bedroom.', 'chunk': {'the bedroom', 'the lights'}, 'action': 'change'}"
    pass

def maths_manager():
    #"do some maths|{'input': 'It is 5082 divided by 9.', 'chunk': {'It'}, 'action': 'divided'}"
    pass

def music_manager(self, input):
    b"music player|{'input': 'Play Blue Swag Shoes by Elvis Presley.', 'chunk': {'Elvis Presley', 'Blue Swag Shoes'}, 'action': 'Play', 'person': 'Elvis Presley'}"
    if input['action']:
        if input['action'].lower() == 'play':
            #self.mqtt_client.publish('flan/in', f"identify the band and song
            music.play(input['input'])
        if input['action'].lower() == 'pause':
            music.stop()
        if input['action'].lower() == 'skip'
            music.skip()

def news_manager():
    #"news|{'input': 'Read me the news headlines.', 'chunk': {'the news headlines', 'me'}, 'action': 'Read'}"
    #b'news|{\'input\': "What\'s the biggest news story of the day?", \'chunk\': {\'the day\', \'the biggest news story\', \'What\'}, \'query\': \'What\', \'date\': \'the day\'}'
    pass

def note_manager():
    #b"notes|{'input': 'Read my notes from my last meeting.', 'chunk': {'my last meeting', 'my notes'}, 'action': 'Read'}"
    pass

def spelling_manager():
    #b"spell checker|{'input': 'How do you spell the quatious?', 'chunk': {'you', 'the quatious'}, 'query': 'How', 'action': 'spell'}"
    pass

def timer_manager(self, input):
    b"timer|{'input': 'Set the timer for 10 minutes.', 'chunk': {'the timer', '10 minutes'}, 'action': 'Set', 'duration': '10 minutes'}"
    timer = None
    if input['action']:
        if input['action'].lower() == 'set':
            timer = CustomTimer()
            timer(input['duration'].lower())
        if input['action'].lower() == 'cancel':
            timer.cancel()
    if input['query']:
        if timer:
            timer.time_left()

def translation_manager():
    #b"translate|{'input': 'How do you say I need to go to work in German?', 'chunk': {'you', 'German', 'work', 'I'}, 'query': 'How', 'action': 'say'}"
    pass

def transcription_manager():
    #b"transcribe|{'input': 'start transcribing my meeting.', 'chunk': {'my meeting'}, 'action': 'start'}"
    pass

def weather_manager():
    #b"weather forecast|{'input': 'Is it going to rain today?', 'chunk': {'it'}, 'action': 'going', 'date': 'today'}"
    #b'weather forecast|{\'input\': "What\'s the weather like in Swansea?", \'chunk\': {\'the weather\', \'Swansea\', \'What\'}, \'query\': \'What\', \'place\': \'Swansea\'}'
    pass