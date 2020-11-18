import logging
import asyncio
import re
from mavsdk import System
from mavsdk.telemetry import *
from mavsdk.action import *
from mavsdk.offboard import *
from enum import Enum
from functools import partial


class Mode(Enum):
    ALTITUDE  = 1
    HEADING   = 2
    POSITION  = 3
    TAKEOFF   = 4
    LAND      = 6
    STATUS    = 7
    SPECIAL   = 8


VERBS = {
    Mode.ALTITUDE: {"climb", "descend", "maintain"},
    Mode.HEADING:  {"turn"},
    Mode.POSITION: {"hold", "direct"},
    Mode.TAKEOFF:  {"clear for takeoff"},
    Mode.LAND:     {"clear to land"}
}

NOUNS = {
    Mode.ALTITUDE: {r"(?P<unit>FL) (?P<val>\d+)", r"(?P<val>\d+) (?P<unit>ft)"},
    Mode.HEADING:  {r"heading (?P<val>\d+)"},
    Mode.POSITION: {r"Ingolstadt Main Station", r"MIQ", r"OTT VOR", r"WLD VOR"}
}

LOCATIONS_NED = {
    "Ingolstadt Main Station": (0, 0, 2),
    "MIQ": (1, 1, 2),
    "OTT VOR": (1, 3, 2),
    "WLD VOR": (3, 0, 2)
}

LOCATIONS_LAT_LONG = {}

def get_arg(pattern, phrase, mode, ned=True):
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
        if mode == Mode.HEADING:
            val = match.group('val')
            arg = int(val)
        if mode == Mode.POSITION:
            arg = LOCATIONS_NED.get(arg) if ned else LOCATIONS_LAT_LONG.get(arg)
        return arg

class Factory:
    def __init__(self, drone):
        self.drone = drone
        self._MISSIONS = {
            Mode.ALTITUDE: self.altitude,
            Mode.HEADING:  self.heading,
            Mode.POSITION: self.goto,
            Mode.TAKEOFF:  self.takeoff,
            Mode.LAND:     self.land
        }

    async def try_action(self, action, condition, error, message):
        if condition:
            logging.info(message)
            return True
        else:
            try:
                await action()
            except error as e:
                logging.error(e)
        await asyncio.sleep(0.1)

    async def fetch(self, *meta):
        action = self._MISSIONS.get(meta[0])
        return partial(action, self.drone, meta[1])

    async def altitude(self, altitude):
        logging.info(f"Changing altitude to {altitude}")
        await asyncio.sleep(0.1)

    async def heading(self, heading):
        logging.info(f"Changing heading to {heading}")
        await asyncio.sleep(0.1)

    async def goto(self, pos):
        logging.info(f"Enroute towards {pos}")
        await asyncio.sleep(0.1)

    async def takeoff(self):
        logging.info(f"Taking off")
        await asyncio.sleep(0.1)

    async def land(self):
        logging.info(f"Inbound for landing")
        await asyncio.sleep(0.1)
