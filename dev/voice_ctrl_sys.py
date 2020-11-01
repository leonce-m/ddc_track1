def foo1(verb, nouns):
    return verb + nouns.join(" ") + ": foo1"


def foo2(verb, nouns):
    return verb + nouns.join(" ") + ": foo2"


def foo3(verb, nouns):
    return verb + nouns.join(" ") + ": foo3"


def foo4(verb, nouns):
    return verb + nouns.join(" ") + ": foo4"


class VIO(object):
    VIO_GRAMMAR_VERBS = [
        ({"climb", "descend", "maintain"}, "ALT", foo1),
        ({"turn"}, "DIR", foo2),
        ({"hold"}, "LOC", foo3),
        ({"direct"}, "LOC", foo4)
    ]
    VIO_GRAMMAR_NOUNS = {
        "ALT": {"FL [0-9]", "[0-9]+ ft"},
        "DIR": {"heading [0-9]"},
        "LOC": {"Ingolstadt Main Station", "MIQ", "OTT VOR", "WLD VOR"}
    }

    def __init__(self, call_sign):
        self.call_sign = call_sign
        self.verbs = self.VIO_GRAMMAR_VERBS
        self.nouns = self.VIO_GRAMMAR_NOUNS

    def find_next_verb(self, token):
        for i, t in enumerate(token):
            for v_type in self.verbs:
                for r in v_type[0]:
                    if r == t:
                        return i, t
        return 0, 0

    def handle_phrase(self, phrase):
        return 0

    def handle_phrase_queue(self, token):
        if len(token) == 0:
            return False
        i, verb = self.find_next_verb(token)
        if not verb:
            return False
        token.pop(i)
        j, temp = self.find_next_verb(token)
        if not temp:
            j = len(token)
        token.insert(i, verb)
        phrase = " ".join(token[i:j+1])
        del token[i:j+1]
        print(phrase)
        return True

    def handle_id(self, token):
        if len(token) > 1 and token[1].isdigit():
            token[0] = token[0] + token[1]
            token.remove(token[1])
        if token[0] == self.call_sign:
            token.remove(token[0])
            return True

    def handle_command(self, command):
        token = command.split()
        if not self.handle_id(token):
            print(f"Call sign '{token[0]}' not recognized")
        else:
            while len(token) > 0:
                if not self.handle_phrase_queue(token):
                    print(f"Command '{token[0]}' not recognized or not executable")
                    break


class VCS(VIO):
    def __init__(self, call_sign, verbose=False):
        super().__init__(call_sign)
        self.verbose = verbose


def main(ARGS):
    vcs = VCS("CityAirbus1234", ARGS.verbose)
    while True:
        command = input()
        if not command:
            break
        # print(command)
        vcs.handle_command(command)

    return 0


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Control PIXHAWK via MavSDK-Python with ATC commands (and respond)")
    parser.add_argument('-vv','--verbose', type=bool, default=False,
                        help="Enable verbose console output for debug purposes")
    ARGS = parser.parse_args()
    main(ARGS)
