from threading import Thread
import pyttsx3

class TTS:
	def __init__(self):
		self.engine = pyttsx3.init()

	def respond(self, utterance):
		thread = Thread(target=self._thread_callback, args=(utterance,))
		thread.start()

	def _thread_callback(self, utterance):
		self.engine.say(utterance)
		self.engine.runAndWait()
