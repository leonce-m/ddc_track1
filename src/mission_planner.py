import re
import logging
import asyncio
import utm
import math
from mavsdk import System, telemetry, action, mission
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
    Mode.POSITION: {r"Ingolstadt Main Station", r"MIQ", r"OTT VOR", r"WLD VOR"},
    Mode.LAND:     {r"(?:runway) (?P<val>\d+) (?P<unit>right|left)"}
}

LOCATIONS_NED = {
    "Ingolstadt Main Station": telemetry.PositionNed(0, 0, -2),
    "MIQ": telemetry.PositionNed(10, 14, -2),
    "OTT VOR": telemetry.PositionNed(-5, 9, -2),
    "WLD VOR": telemetry.PositionNed(3, 20, -2),
    "26 right": telemetry.PositionNed(0, 5, 0),
    "26 left": telemetry.PositionNed(0, -5, 0)
}

LOCATIONS_LAT_LON = {
    "Ingolstadt Main Station":  telemetry.Position(48.688433, 11.525667, 367, 0),
    "MIQ": telemetry.Position(48.688383, 11.525417, 367, 0),
    "OTT VOR": telemetry.Position(48.688600, 11.525283, 367, 0),
    "WLD VOR": telemetry.Position(48.688667, 11.525567, 367, 0),
    "26 right": telemetry.Position(48.688583, 11.525567, 367, 0),
    "26 left": telemetry.Position(48.688583, 11.525667, 367, 0)
}

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
            arg = LOCATIONS_NED.get(arg) if ned else LOCATIONS_LAT_LON.get(arg)
        if mode == Mode.LAND:
            arg = ' '.join([match.group('val'), match.group('unit')])
            arg = LOCATIONS_NED.get(arg) if ned else LOCATIONS_LAT_LON.get(arg)
        return arg

class Navigator:
    def __init__(self, drone: System):
        self.drone = drone
        self.mission_plan = None

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
            return self.mission_change_altitude(*args)
        if mode == Mode.POSITION:
            return self.mission_fly_direct(*args)
        if mode == Mode.HEADING:
            return self.mission_fly_heading(*args)

    async def get_position(self) -> telemetry.Position:
        async for position in self.drone.telemetry.position():
            while not position:
                await asyncio.sleep(0.1)
            return position

    async def upload_and_start(self, mission_plan):
        await self.drone.mission.clear_mission()
        await self.drone.mission.upload_mission(mission_plan)
        async for mission_progress in self.drone.mission.mission_progress():
            if mission_progress.total > 0:
                break
            await asyncio.sleep(0.1)
        await self.drone.mission.start_mission()
        await asyncio.sleep(0.1)

    async def mission_change_altitude(self, target_alt: float):
        logging.info(f"Change target altitude to {target_alt}m ASL")
        if self.mission_plan is not None:
            for item in self.mission_plan.mission_items:
                item.relative_altitude = target_alt
                logging.debug(item)
        else:
            pos = await self.get_position()
            new_wp = mission.MissionItem(
                pos.latitude_deg,
                pos.longitude_deg,
                target_alt,
                1.0,
                False,
                float('nan'),
                float('nan'),
                mission.MissionItem.CameraAction.NONE,
                5.0,
                float('nan')
            )
            logging.debug(new_wp)
            self.mission_plan = mission.MissionPlan([new_wp])
        await self.upload_and_start(self.mission_plan)

    async def mission_fly_heading(self, heading: int):
        logging.info(f"Turning to {heading}")
        pos_gps = await self.get_position()
        if self.mission_plan is not None:
            target_alt = self.mission_plan.mission_items[0].relative_altitude_m
        else:
            target_alt = pos_gps.relative_altitude_m
        pos_utm = utm.from_latlon(pos_gps.latitude_deg, pos_gps.longitude_deg)
        tgt_utm = (pos_utm[0] + math.sin(math.radians(heading)) * 5, pos_utm[1] + math.cos(math.radians(heading)) * 5)
        tgt_gps = utm.to_latlon(*tgt_utm, pos_utm[2], pos_utm[3])
        new_wp = mission.MissionItem(
            *tgt_gps,
            target_alt,
            1.0,
            False,
            float('nan'),
            float('nan'),
            mission.MissionItem.CameraAction.NONE,
            5.0,
            float('nan')
        )
        self.mission_plan = mission.MissionPlan([new_wp])
        await self.upload_and_start(self.mission_plan)

    async def mission_fly_direct(self, position: telemetry.Position):
        logging.info(f"Set enroute towards N{position.latitude_deg} E{position.longitude_deg}")
        pos_gps = await self.get_position()
        if self.mission_plan is not None:
            target_alt = self.mission_plan.mission_items[0].relative_altitude_m
        else:
            target_alt = pos_gps.relative_altitude_m
        new_wp = mission.MissionItem(
            position.latitude_deg,
            position.longitude_deg,
            target_alt,
            1.0,
            False,
            float('nan'),
            float('nan'),
            mission.MissionItem.CameraAction.NONE,
            5.0,
            float('nan')
        )
        self.mission_plan = mission.MissionPlan([new_wp])
        await self.upload_and_start(self.mission_plan)

    async def command_takeoff(self):
        logging.info("Arming drone")
        async for armed in self.drone.telemetry.armed():
            if await self.try_action(self.drone.action.arm, armed, action.ActionError, "Arming successful"):
                return
        await asyncio.sleep(1)
        logging.info("Taking off")
        async for in_air in self.drone.telemetry.in_air():
            if await self.try_action(self.drone.action.takeoff, in_air, action.ActionError, "Takeoff successful"):
                break
        await asyncio.sleep(0.1)

    async def command_landing(self, position=None):
        logging.info(f"Inbound for landing at {position}")
        await asyncio.sleep(0.1)
        if position is not None:
            new_wp = mission.MissionItem(
                position.latitude_deg,
                position.longitude_deg,
                0,
                1.0,
                False,
                float('nan'),
                float('nan'),
                mission.MissionItem.CameraAction.NONE,
                5.0,
                float('nan')
            )
            self.mission_plan = mission.MissionPlan([new_wp])
            await self.upload_and_start(self.mission_plan)
            await self.drone.mission.is_mission_finished()
        await asyncio.sleep(1)
        logging.info(f"Starting final descent")
        async for landed in self.drone.telemetry.landed_state():
            if await self.try_action(self.drone.action.land, landed, action.ActionError, "Landing succesful"):
                break
        await asyncio.sleep(1)
        logging.info("Disarming drone")
        async for armed in self.drone.telemetry.armed():
            if await self.try_action(self.drone.action.disarm, not armed, action.ActionError, "Disarming successful"):
                return
