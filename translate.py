from TranslationLayer import translator
import time

translate = translator.translator()
translate.run()

while True:
    time.sleep(1)
