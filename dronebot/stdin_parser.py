import logging
import re
from threading import Thread

import pyttsx3
from text_to_num import alpha2digit
from dronebot import config_logging
from dronebot.mission_planner import Vocabulary


class CommunicationError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        # return f"{type(self).__name__}: {self.message}"
        return self.message


class Parser(object):
    """
    Converts stdin command strings from deepspeech into parsed command data.
    """

    def __init__(self, call_sign):
        self.call_sign = call_sign
        self.tts_engine = pyttsx3.init()
        self.vocab = Vocabulary()
        self.response = ""
        self.command_list = list()

    def find_next_verb(self, phrase):
        for mode in self.vocab.VERBS.keys():
            for r in self.vocab.VERBS.get(mode):
                match = re.search(r, phrase)
                if match:
                    return match.start(), match.end(), r, mode
        return 0, 0, 0, 0

    def handle_response(self, phrase, mode=None):
        # TODO: implement proper response decision tree
        if mode:
            pass
        self.response += " " + phrase

    def handle_response_queue(self):
        if len(self.response) > 0:
            sentence = f"{self.response.strip().capitalize()}, {self.call_sign}."
            logging.info("Response: " + sentence)
            tts_thread = Thread(target=self.tts, args=(sentence,))
        else:
            logging.info(f"Response: {self.call_sign}.")
            tts_thread = Thread(target=self.tts, args=(self.call_sign,))
        tts_thread.start()
        self.response = ""

    def tts(self, utterance):
        self.tts_engine.say(utterance)
        self.tts_engine.runAndWait()

    def handle_phrase(self, phrase, mode):
        found_match = False
        for pattern in self.vocab.NOUNS.get(mode, {""}):
            if pattern:
                arg = self.vocab.get_arg(pattern, phrase, mode)
                if arg:
                    self.command_list.append((mode, arg))
                    found_match = True
            else:
                logging.debug(f"Mode is without expected parameters")
                self.command_list.append((mode, None))
        if not found_match:
            logging.debug(CommunicationError(f"Phrase '{phrase}' does not contain expected parameters"))

    def handle_phrase_queue(self, phrase):
        if len(phrase) == 0:
            return
        i1, i2, verb1, mode1 = self.find_next_verb(phrase)
        if not verb1:
            raise CommunicationError(f"Phrase '{phrase}' does not contain known command")
        j1, _, verb2, mode2 = self.find_next_verb(phrase[i2:])
        if not verb2:
            j1 = len(phrase)
        self.handle_phrase(phrase[i1:j1], mode1)
        self.handle_response(phrase[i1:j1], mode1)
        self.handle_phrase_queue(phrase[j1:])

    def handle_id(self, cmd_string):
        token = cmd_string.split()
        if len(token) > 1 and token[1].isdigit():
            token[0] += token[1]
            token.remove(token[1])
        if token[0] != self.call_sign:
            raise CommunicationError(f"Call sign '{token[0]}' not recognized")

    def handle_command(self, cmd_string):
        cmd_string = re.sub(r"(?<=\d)\s(?=\d)", "", alpha2digit(cmd_string, "en", True))
        self.command_list.clear()
        try:
            self.handle_id(cmd_string)
        except CommunicationError as e:
            logging.error(e)
        else:
            try:
                self.handle_phrase_queue(cmd_string)
            except CommunicationError as e:
                logging.error(e)
                self.handle_response("Say again")
            except Exception:
                raise
            finally:
                self.handle_response_queue()
        return self.command_list


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Control PIXHAWK via MavSDK-Python with ATC commands (and respond)")
    parser.add_argument('-c', '--call_sign', default="CityAirbus1234",
                        help="Set custom call sign")
    ARGS = parser.parse_args()

    config_logging.config_logging_stdout(logging.DEBUG)

    vio = Parser(ARGS.call_sign)
    while True:
        command = input()
        if not command:
            break
        logging.debug(vio.handle_command(command))
