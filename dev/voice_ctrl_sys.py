def foo1(verb, nouns):
    print(verb + nouns.join(" ") + ": foo1")


def foo2(verb, nouns):
    print(verb + nouns.join(" ") + ": foo2")


def foo3(verb, nouns):
    print(verb + nouns.join(" ") + ": foo3")


def foo4(verb, nouns):
    print(verb + nouns.join(" ") + ": foo4")


class VCS(object):
    def __init__(self, call_sign):
        self.call_sign = call_sign
        self.verbs = [
            ({"climb", "descend", "maintain"},  "ALT", foo1),
            ({"turn"},                          "DIR", foo2),
            ({"hold"},                          "LOC", foo3),
            ({"direct"},                        "LOC", foo4)
        ]
        self.nouns = [
            {"ALT": {"FL [0-9]", "[0-9]+ ft"}},
            {"DIR": {"heading [0-9]"}},
            {"LOC": {"Ingolstadt Main Station", "MIQ", "OTT VOR", "WLD VOR"}}
        ]

    def find_first_of(self, token, regex_list):
        for i, t in enumerate(token):
            for r in regex_list:
                if r == t:
                    return i, t

    def handle_id(self, token):
        if len(token) > 1 and token[1].isdigit():
            token[0] = token[0] + token[1]
            token.remove(token[1])
        if token[0] == self.call_sign:
            token.remove(token[0])
            return True

    def handle_phrase(self, token):
        if len(token) == 0:
            return False
        i, t = self.find_first_of(token, self.vcs_dialect[0][0])
        print(i, t)
        token.pop(i)
        return t

    def consume_command(self, command):
        token = command.split()
        if not self.handle_id(token):
            print(f"Call sign '{token[0]}' not recognized")
        else:
            while len(token) > 0:
                if not self.handle_phrase(token):
                    print(f"Command '{token[0]}' not recognized or not executable")
                    break


def main():
    vcs = VCS("CityAirbus1234")
    while True:
        command = input()
        if not command:
            break
        # print(command)
        vcs.consume_command(command)

    return 0


if __name__ == '__main__':
    main()
