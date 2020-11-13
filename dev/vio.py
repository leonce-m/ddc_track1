import logging
import re
from mavsdk.offboard import *
from dev import misc


class VioComError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return f"{type(self).__name__}: {self.message}"

class Mode(Enum):
    ALTITUDE  = 1
    DIRECTION = 2
    POSITION  = 3
    TAKEOFF   = 4
    LAND      = 6
    STATUS    = 7
    SPECIAL   = 8


VERBS = {
    Mode.ALTITUDE:  {"climb", "descend", "maintain"},
    Mode.DIRECTION: {"turn"},
    Mode.POSITION:  {"hold", "direct"}
}

NOUNS = {
    Mode.ALTITUDE:  {r"(?P<unit>FL) (?P<val>\d+)", r"(?P<val>\d+) (?P<unit>ft)"},
    Mode.DIRECTION: {r"heading (?P<val>\d+)"},
    Mode.POSITION:  {r"Ingolstadt Main Station", r"MIQ", r"OTT VOR", r"WLD VOR"}
}

LOCATIONS_NED = {
    "Ingolstadt Main Station": (0, 0, 2),
    "MIQ": (1, 1, 2),
    "OTT VOR": (1, 3, 2),
    "WLD VOR": (3, 0, 2)
}

LOCATIONS_LAT_LONG = {}


class Parser(object):

    def __init__(self, call_sign, ned=True):
        self.call_sign = call_sign
        self.verbs = VERBS
        self.nouns = NOUNS
        if ned:
            self.locations = LOCATIONS_NED
        else:
            self.locations = LOCATIONS_LAT_LONG

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
            match = re.search(pattern, phrase)
            if match:
                arg = match.group(0)
                if mode == Mode.ALTITUDE:
                    val = match.group('val')
                    unit = match.group('unit')
                    if unit == "FL":
                        arg = float(val) * 30.48
                    elif unit == "ft":
                        arg = float(val) * 0.3048
                if mode == Mode.DIRECTION:
                    arg = int(arg)
                if mode == Mode.POSITION:
                    arg = self.locations.get(arg)
                self.command_list.append((mode, arg))
                found_match = True
        if not found_match:
            raise VioComError(f"Phrase '{phrase}' does not contain known parameters")

    def handle_phrase_queue(self, token):
        if len(token) == 0:
            return
        i, verb1, mode1 = self.find_next_verb(token)
        if not verb1:
            raise VioComError(f"Phrase '{' '.join(token)}' does not contain known command")
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
            raise VioComError(f"Call sign '{token[0]}' not recognized")
        token.remove(token[0])

    def handle_command(self, cmd_string):
        token = cmd_string.split()
        self.command_list.clear()
        try:
            self.handle_id(token)
        except VioComError as e:
            logging.error(e)
        else:
            try:
                self.handle_phrase_queue(token)
            except VioComError as e:
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

    misc.config_logging_stdout(logging.DEBUG)

    vio = Parser(ARGS.call_sign)
    while True:
        command = input()
        if not command:
            break
        # print(command)
        vio.handle_command(command)
