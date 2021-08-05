from threading import Thread
import queue
import logging
import pyttsx3

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class TTS(Thread):
    def __init__(self):
        super().__init__()
        self.queue = queue.Queue()
        self.daemon = True
        self.start()

    def run(self):
        tts_engine = pyttsx3.init()
        tts_engine.startLoop(False)
        t_running = True
        while t_running:
            if self.queue.empty():
                tts_engine.iterate()
            else:
                data = self.queue.get()
                if data == "exit":
                    t_running = False
                else:
                    tts_engine.say(data)
        tts_engine.endLoop()

    def respond(self, utterance):
        logger.info(f"Respond: {utterance}")
        self.queue.put(utterance)
