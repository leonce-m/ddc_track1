import logging

def foo1(verb, nouns):
    return verb + nouns.join(" ") + ": foo1"


def foo2(verb, nouns):
    return verb + nouns.join(" ") + ": foo2"


def foo3(verb, nouns):
    return verb + nouns.join(" ") + ": foo3"


def foo4(verb, nouns):
    return verb + nouns.join(" ") + ": foo4"


class VioComError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message

class Grammar(object):
    VERBS = [
        ({"climb", "descend", "maintain"}, "ALT", foo1),
        ({"turn"}, "DIR", foo2),
        ({"hold"}, "LOC", foo3),
        ({"direct"}, "LOC", foo4)
    ]
    NOUNS = {
        "ALT": {"FL [0-9]", "[0-9]+ ft"},
        "DIR": {"heading [0-9]"},
        "LOC": {"Ingolstadt Main Station", "MIQ", "OTT VOR", "WLD VOR"}
    }

class Parser(object):

    def __init__(self, call_sign, verbose=True):
        self.call_sign = call_sign
        self.verbose = verbose
        self.verbs = Grammar.VERBS
        self.nouns = Grammar.NOUNS
        self.phrase = ""

    def find_next_verb(self, token):
        for i, t in enumerate(token):
            for v_type in self.verbs:
                for r in v_type[0]:
                    if r == t:
                        return i, t
        return 0, 0

    def handle_response(self, phrase):
        self.phrase += " " + phrase

    def handle_response_queue(self):
        logging.info(f"Response: {self.call_sign},{self.phrase}.")
        self.phrase = ""

    def handle_phrase(self, phrase):
        return 0

    def handle_phrase_queue(self, token):
        if len(token) == 0:
            return
        i, verb = self.find_next_verb(token)
        if not verb:
            raise VioComError("unable")
        token.pop(i)
        j, temp = self.find_next_verb(token)
        if not temp:
            j = len(token)
        token.insert(i, verb)
        phrase = " ".join(token[0:j+1])
        del token[0:j+1]
        self.handle_response(phrase)
        self.handle_phrase(phrase)
        self.handle_phrase_queue(token)

    def handle_id(self, token):
        if len(token) > 1 and token[1].isdigit():
            token[0] += token[1]
            token.remove(token[1])
        if token[0] != self.call_sign:
            raise VioComError(f"Call sign '{token[0]}' not recognized")
        token.remove(token[0])

    def handle_command(self, command):
        token = command.split()
        try:
            self.handle_id(token)
        except VioComError as e:
            logging.error(e)
        else:
            try:
                self.handle_phrase_queue(token)
            except VioComError as e:
                self.handle_response(e.message)
            finally:
                self.handle_response_queue()


def main(ARGS):
    vio = Parser(ARGS.call_sign, ARGS.verbose)
    while True:
        command = input()
        if not command:
            break
        # print(command)
        vio.handle_command(command)

    return 0


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Control PIXHAWK via MavSDK-Python with ATC commands (and respond)")
    parser.add_argument('-s', '--call_sign', default="CityAirbus1234",
                        help="Set custom call sign")
    ARGS = parser.parse_args()
    main(ARGS)
