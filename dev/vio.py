import logging
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
    Mode.POSITION:  {"hold, direct"}
}

NOUNS = {
    Mode.ALTITUDE:  {"FL [0-9]", "[0-9]+ ft"},
    Mode.DIRECTION: {"heading [0-9]"},
    Mode.POSITION:  {"Ingolstadt Main Station", "MIQ", "OTT VOR", "WLD VOR"}
}

LOCATIONS_NED = {
    "Ingolstadt Main Station": (0, 0, 2),
    "MIQ": (1, 1, 2),
    "OTT VOR": (1, 3, 2),
    "WLD VOR": (3, 0, 2)
}


def fl_to_m(alt):
    return alt * 30.48

def ft_to_m(alt):
    return alt * 0.3048


class Parser(object):

    def __init__(self, call_sign):
        self.call_sign = call_sign
        self.verbs = VERBS
        self.nouns = NOUNS
        self.phrase = ""
        self.command_list = list()

    def find_next_verb(self, token):
        for i, t in enumerate(token):
            for mode in self.verbs.keys():
                for r in self.verbs[mode]:
                    if r == t:
                        return i, t, mode.name
        return 0, 0, 0

    def handle_response(self, phrase, mode=None):
        # TODO: implement proper response decision tree
        if mode:
            pass
        self.phrase += " " + phrase

    def handle_response_queue(self):
        if len(self.phrase) > 0:
            logging.info(f"Response: {self.phrase.strip().capitalize()}, {self.call_sign}.")
        else:
            logging.info(f"Response: {self.call_sign}.")
        self.phrase = ""

    def handle_phrase(self, phrase, mode):
        # TODO: implement proper command selection based on v_type[2]
        for regex in self.nouns.get(mode, ""):
            pass
        # TODO: regex search for noun params
        # TODO: convert FL and ft to m
        args = []
        self.command_list.append((mode, args))

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
        self.handle_response(phrase, mode1)
        self.handle_phrase(phrase, mode1)
        self.handle_phrase_queue(token)

    def handle_id(self, token):
        if len(token) > 1 and token[1].isdigit():
            token[0] += token[1]
            token.remove(token[1])
        if token[0] != self.call_sign:
            raise VioComError(f"Call sign '{token[0]}' not recognized")
        token.remove(token[0])

    def handle_command(self, command_string):
        token = command_string.split()
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
