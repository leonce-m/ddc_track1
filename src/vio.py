import logging
import re
from .misc import *
from .mission import *


class CommunicationError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        # return f"{type(self).__name__}: {self.message}"
        return self.message


class Parser(object):
    def __init__(self, call_sign, ned=True):
        self.call_sign = call_sign
        self.verbs = VERBS
        self.nouns = NOUNS
        self.ned = ned
        self.response = ""
        self.command_list = list()

    def find_next_verb(self, token):
        for i, t in enumerate(token):
            for mode in self.verbs.keys():
                for r in self.verbs.get(mode):
                    if r == t:
                        return i, t, mode
        return 0, 0, 0

    def handle_response(self, phrase, mode=None):
        # TODO: implement proper response decision tree
        if mode:
            pass
        self.response += " " + phrase

    def handle_response_queue(self):
        if len(self.response) > 0:
            logging.info(f"Response: {self.response.strip().capitalize()}, {self.call_sign}.")
        else:
            logging.info(f"Response: {self.call_sign}.")
        self.response = ""

    def handle_phrase(self, phrase, mode):
        found_match = False
        for pattern in self.nouns.get(mode):
            arg = get_arg(pattern, phrase, mode, self.ned)
            if arg:
                self.command_list.append((mode, arg))
                found_match = True
        if not found_match:
            logging.debug(CommunicationError(f"Phrase '{phrase}' does not contain known parameters"))

    def handle_phrase_queue(self, token):
        if len(token) == 0:
            return
        i, verb1, mode1 = self.find_next_verb(token)
        if not verb1:
            raise CommunicationError(f"Phrase '{' '.join(token)}' does not contain known command")
        token.pop(i)
        j, verb2, mode2 = self.find_next_verb(token)
        if not verb2:
            j = len(token)
        token.insert(i, verb1)
        phrase = " ".join(token[0:j+1])
        del token[0:j+1]
        self.handle_phrase(phrase, mode1)
        self.handle_response(phrase, mode1)
        self.handle_phrase_queue(token)

    def handle_id(self, token):
        if len(token) > 1 and token[1].isdigit():
            token[0] += token[1]
            token.remove(token[1])
        if token[0] != self.call_sign:
            raise CommunicationError(f"Call sign '{token[0]}' not recognized")
        token.remove(token[0])

    def handle_command(self, cmd_string):
        token = cmd_string.split()
        self.command_list.clear()
        try:
            self.handle_id(token)
        except CommunicationError as e:
            logging.error(e)
        else:
            try:
                self.handle_phrase_queue(token)
            except CommunicationError as e:
                logging.error(e)
                self.handle_response("Say again")
            finally:
                self.handle_response_queue()
        return self.command_list


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Control PIXHAWK via MavSDK-Python with ATC commands (and respond)")
    parser.add_argument('-c', '--call_sign', default="CityAirbus1234",
                        help="Set custom call sign")
    ARGS = parser.parse_args()

    config_logging_stdout(logging.DEBUG)

    vio = Parser(ARGS.call_sign)
    while True:
        command = input()
        if not command:
            break
        # print(command)
        vio.handle_command(command)
