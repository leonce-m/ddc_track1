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
        with open((Path(__file__).parent / 'vocabulary.yaml').resolve()) as file:
            vocab = yaml.load(file, Loader=yaml.FullLoader)

        setattr(self, 'MODE', IntEnum('MODE', vocab.get('MODES')))
        setattr(self, 'VERBS', dict((self.MODE[key], set(val)) for key, val in vocab.get('VERBS').items()))
        setattr(self, 'NOUNS', dict((self.MODE[key], set(val)) for key, val in vocab.get('NOUNS').items()))
        setattr(self, 'POSITIONS', dict((key, telemetry.Position(*val)) for key, val in vocab.get('POSITIONS').items()))

    def get_arg(self, pattern, phrase, mode):
        match = re.search(pattern, phrase)
        if match:
            arg = match.group(0)
            if mode == self.MODE.ALTITUDE:
                val = match.group('val')
                unit = match.group('unit')
                if unit == "FL":
                    arg = float(val) * 30.48 * 0.01
                elif unit == "ft":
                    arg = float(val) * 0.3048 * 0.01
            if mode == self.MODE.HEADING:
                val = match.group('val')
                arg = int(val)
            if mode == self.MODE.POSITION:
                arg = self.POSITIONS.get(arg)
            if mode == self.MODE.LAND:
                arg = ' '.join([match.group('val'), match.group('unit')])
                arg = self.POSITIONS.get(arg)
            return arg
