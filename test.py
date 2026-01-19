from TranslationLayer import MQTTswitchboard, translator, vits
#from ActionLayer import clock

translate = translator.translator()
switchboard = MQTTswitchboard.MQTTMessages()
speak = vits.voicer()

translate.run()
switchboard.run()
speak.run()


#tool_clock = clock.clock()
