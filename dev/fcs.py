class FCS(object):
    def __init__(self, call_sign):
        self.call_sign = call_sign

    def handle_id(self, token):
        if len(token) > 1 and token[1].isdigit():
            token[0] = token[0] + token[1]
            token.remove(token[1])
        if token[0] == self.call_sign:
            token.remove(token[0])
            return True

    @staticmethod
    def handle_phrase(token):
        if len(token) == 0:
            return False

    def parse(self, command):
        token = command.split()
        if not self.handle_id(token):
            print(f"Call sign '{token[0]}' not recognized")
        else:
            while len(token) > 0:
                if not self.handle_phrase(token):
                    print(f"Command '{token[0]}' not recognized or not executable")
                    break


def main():
    fcs = FCS("CityAirbus1234")
    while True:
        command = input()
        if not command:
            break
        # print(command)
        fcs.parse(command)

    return 0


if __name__ == '__main__':
    main()
