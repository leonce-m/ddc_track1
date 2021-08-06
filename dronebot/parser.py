import logging
import re

from text_to_num import alpha2digit

from dronebot import config_logging
from dronebot.vocab import Vocabulary

logger = logging.getLogger(__name__.upper())

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
        self.vocab = Vocabulary()
        self.command_list = list()

    def find_next_verb(self, phrase):
        for mode in self.vocab.VERBS.keys():
            for r in self.vocab.VERBS.get(mode):
                match = re.search(r, phrase)
                if match:
                    # logger.debug(match)
                    return match.start(), match.end(), r, mode
        return 0, 0, 0, 0

    def handle_phrase(self, phrase, mode):
        logger.debug(f"Handle phrase '{phrase}'")
        phrase = re.sub(r"(?<=\d)\s(?=\d)", "", alpha2digit(phrase, "en", True))
        found_match = False
        for pattern in self.vocab.NOUNS.get(mode, {""}):
            if pattern:
                kwargs = self.vocab.get_kwargs(pattern, phrase, mode)
                if kwargs:
                    self.command_list.append(kwargs)
                    found_match = True
            else:
                logger.debug(f"Mode is without expected parameters")
                kwargs = {'phrase': phrase, 'mode': mode}
                self.command_list.append(kwargs)
        if not found_match:
            logger.debug(CommunicationError(f"Phrase '{phrase}' does not contain expected parameters"))

    def handle_phrase_queue(self, phrase):
        if len(phrase) == 0:
            return
        i1, i2, verb1, mode = self.find_next_verb(phrase)
        if not verb1:
            raise CommunicationError(f"Phrase '{phrase}' does not contain known command")
        j1, _, verb2, _ = self.find_next_verb(phrase[i2:])
        if not verb2:
            j1 = len(phrase)
        self.handle_phrase(phrase[i1:i2+j1], mode)
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
            self.handle_phrase_queue(cmd_string)
        except CommunicationError as e:
            logger.error(e)
            self.command_list.append(None)
        return self.command_list


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Control PIXHAWK via MavSDK-Python with ATC commands (and respond)")
    parser.add_argument('-c', '--call_sign', default="cityairbus1234",
                        help="Set custom call sign")
    ARGS = parser.parse_args()
    config_logging.config_logging_stdout(logging.DEBUG, __name__)

    vio = Parser(ARGS.call_sign)
    while True:
        command = input()
        if not command:
            break
        vio.handle_command(command)
