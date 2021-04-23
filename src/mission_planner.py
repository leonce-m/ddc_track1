import re
import logging
import asyncio
from mavsdk import System, telemetry, action, offboard, mission
from enum import Enum


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
    "Ingolstadt Main Station": telemetry.PositionNed(0, 0, -2),
    "MIQ": telemetry.PositionNed(1, 1, -2),
    "OTT VOR": telemetry.PositionNed(1, 3, -2),
    "WLD VOR": telemetry.PositionNed(3, 0, -2)
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

class NavigatorNed:
    def __init__(self, drone: System):
        self.drone = drone
        self.min_alt = 1
        self.max_velocity = 0.5
        self.target_alt = 1
        self.hold_task = None
        self.hold_mode = None

    @staticmethod
    async def try_action(action_coro, condition, error, message):
        if condition:
            logging.info(message)
            return True
        else:
            try:
                await action_coro()
            except error as e:
                logging.error(e)
        await asyncio.sleep(0.1)

    def fetch_command_coro(self, mode: Mode, *args):
        if mode == Mode.ALTITUDE:
            return self.set_target_alt(*args)
        if mode == Mode.POSITION:
            return self.altitude_position_ned(*args)
        if mode == Mode.HEADING:
            return self.altitude_heading(*args)

    async def get_pos_vel_ned(self):
        async for pos_vel_ned in self.drone.telemetry.position_velocity_ned():
            while not pos_vel_ned:
                await asyncio.sleep(0.1)
            return pos_vel_ned

    async def set_target_alt(self, target_alt: float):
        self.target_alt = max(target_alt, self.min_alt)

    async def altitude_heading(self, heading: int):
        logging.info(f"Change heading to {heading} while holding {self.target_alt}m ASL")
        await asyncio.sleep(0.1)

    async def altitude_position_ned(self, pos_ned: telemetry.PositionNed):
        logging.info(f"Set enroute towards {pos_ned.north_m}m N, {pos_ned.east_m}m E while holding {self.target_alt}m ASL")
        await asyncio.sleep(0.1)

    async def command_takeoff(self):
        logging.info(f"Taking off")
        await asyncio.sleep(0.1)

    async def command_landing(self):
        logging.info(f"Inbound for landing")
        await asyncio.sleep(0.1)