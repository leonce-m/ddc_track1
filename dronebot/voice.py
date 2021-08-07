import asyncio
import logging
import queue
from concurrent.futures import ThreadPoolExecutor
from threading import Thread

import pyttsx3

logger = logging.getLogger(__name__.upper())


class Voice:
    atc = ""
    tts = None
    tp_exec = None

    def __init__(self, *, atc=None):
        if atc:
            Voice.atc = atc
        if not self.tts:
            Voice.tts = TTS()
        if not self.tp_exec:
            Voice.tp_exec = ThreadPoolExecutor()
        self.phrases = list()

    async def speak(self, quick_phrase="", *, full=False):
        self.phrases.append(quick_phrase) if quick_phrase else None
        if len(self.phrases) > 0 or full:
            sentence = (f"{self.atc.capitalize()}, " if full else "")
            sentence += (f"{', '.join(self.phrases)}, " if len(self.phrases) > 0 else "")
            sentence += "Cityairbus alpha india romeo one."
            await asyncio.get_event_loop().run_in_executor(self.tp_exec, self.tts.respond, sentence.capitalize())
            self.phrases.clear()


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
        logger.info(f"Respond: '{utterance}'")
        self.queue.put(utterance)
