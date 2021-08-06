import re
from enum import IntEnum
from pathlib import Path

import yaml
from mavsdk import telemetry


class Vocabulary:
    """
    Container class for vocabulary loaded from a YAML config file.
    @DynamicAttrs
    """

    def __init__(self):
        with open((Path(__file__).parent / 'vocab.yaml').resolve()) as file:
            vocab = yaml.load(file, Loader=yaml.FullLoader)

        setattr(self, 'MODE', IntEnum('MODE', vocab.get('MODES')))
        setattr(self, 'VERBS', dict((self.MODE[key], set(val)) for key, val in vocab.get('VERBS').items()))
        setattr(self, 'NOUNS', dict((self.MODE[key], set(val)) for key, val in vocab.get('NOUNS').items()))
        setattr(self, 'POSITIONS', dict((key, telemetry.Position(*val)) for key, val in vocab.get('POSITIONS').items()))

    def get_kwargs(self, pattern, phrase, mode):
        match = re.search(pattern, phrase)
        if match:
            command = {'match': match.group(0), 'phrase': phrase, 'mode': mode}
            if mode == self.MODE.ALTITUDE:
                val = match.group('val')
                unit = match.group('unit')
                if unit == "flightlevel":
                    command[str(mode)] = float(val) * 30.48 * 0.01
                elif unit == "ft":
                    command[str(mode)] = float(val) * 0.3048 * 0.01
            if mode == self.MODE.HEADING:
                command[str(mode)] = int(match.group('val'))
            if mode == self.MODE.POSITION:
                command[str(mode)] = self.POSITIONS.get(command['match'])
            if mode == self.MODE.CLEARANCE:
                clearance = {'type': match.group('type')}
                if clearance['type'] == 'route':
                    clearance['route'] = None
                    # TODO: add loading flight plan from vocab.yaml
                if clearance['type'] in ['ils', 'land']:
                    clearance['description'] = ' '.join([match.group('val'), match.group('unit')])
                    clearance['position'] = self.POSITIONS.get(clearance['description'])
                command[str(mode)] = clearance
            if mode == self.MODE.CONTACT:
                command[str(mode)] = match.group('val')
            if mode == self.MODE.CONDITION:
                command[str(mode)] = self.POSITIONS.get(match.group('val'))
            if mode == self.MODE.REPORT:
                command[str(mode)] = match.group('val')
            return command
