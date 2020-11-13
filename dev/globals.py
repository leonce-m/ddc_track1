from enum import Enum


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