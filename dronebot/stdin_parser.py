import logging
import re

from text_to_num import alpha2digit
from dronebot import config_logging
from dronebot.vocabulary import Vocabulary
from dronebot.state_machine import FlightState


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

    def __init__(self, call_sign, tts):
        self.call_sign = call_sign
        self.atc = "manching tower"
        self.tts = tts
        self.response = ""
        self.vocab = Vocabulary()
        self.command_list = list()
        self.flight_state = FlightState(self)

    def find_next_verb(self, phrase):
        for mode in self.vocab.VERBS.keys():
            for r in self.vocab.VERBS.get(mode):
                match = re.search(r, phrase)
                if match:
                    return match.start(), match.end(), r, mode
        return 0, 0, 0, 0

    def handle_response(self, phrase):
        self.response += " " + phrase

    def handle_response_queue(self, full=False):
        if len(self.response) > 0 or full:
            sentence = (f"{self.atc.capitalize()}, " if full else "")
            sentence += (f"{self.response.strip().capitalize()}, " if len(self.response) > 0 else "")
            sentence += f"{self.call_sign}."
            self.tts.respond(sentence)
            self.response = ""

    def handle_phrase(self, phrase, mode):
        phrase = re.sub(r"(?<=\d)\s(?=\d)", "", alpha2digit(phrase, "en", True))
        found_match = False
        for pattern in self.vocab.NOUNS.get(mode, {""}):
            if pattern:
                arg = self.vocab.get_arg(pattern, phrase, mode)
                if arg:
                    self.flight_state.update(phrase, mode, arg)
                    found_match = True
            else:
                logging.debug(f"Mode is without expected parameters")

                self.flight_state.update(phrase, mode, None)
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
        self.handle_phrase_queue(phrase[j1:])

    def handle_id(self, cmd_string):
        cmd_string = re.sub(r"(?<=\d)\s(?=\d)", "", alpha2digit(cmd_string, "en", True))
        token = cmd_string.split()
        if len(token) > 1 and token[1].isdigit():
            token[0] += token[1]
            token.remove(token[1])
        if token[0] != self.call_sign:
            raise CommunicationError(f"Call sign '{token[0]}' not recognized")

    def handle_command(self, cmd_string):
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
    from dronebot.voice_response import TTS
    parser = argparse.ArgumentParser(description="Control PIXHAWK via MavSDK-Python with ATC commands (and respond)")
    parser.add_argument('-c', '--call_sign', default="cityairbus1234",
                        help="Set custom call sign")
    ARGS = parser.parse_args()
    logger = config_logging.config_logging_stdout(logging.DEBUG, __name__)

    vio = Parser(ARGS.call_sign, TTS())
    while True:
        command = input()
        if not command:
            break
        vio.handle_command(command)
