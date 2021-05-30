import re
import logging
import asyncio
import traceback
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
    "26 right": telemetry.PositionNed(0, 5, -1),
    "26 left": telemetry.PositionNed(0, -5, -1)
}

LOCATIONS_LAT_LON = {
    "Ingolstadt Main Station":  telemetry.Position(48.688433, 11.525667, 377, 0),
    "MIQ": telemetry.Position(48.688383, 11.525417, 377, 0),
    "OTT VOR": telemetry.Position(48.688600, 11.525283, 377, 0),
    "WLD VOR": telemetry.Position(48.688667, 11.525567, 377, 0),
    "26 right": telemetry.Position(48.688583, 11.525567, 372, 0),
    "26 left": telemetry.Position(48.688583, 11.525667, 372, 0)
}

def get_arg(pattern, phrase, mode, ned=True):
    match = re.search(pattern, phrase)
    if match:
        arg = match.group(0)
        if mode == Mode.ALTITUDE:
            val = match.group('val')
            unit = match.group('unit')
            if unit == "FL":
                arg = float(val) * 30.48 * 0.01
            elif unit == "ft":
                arg = float(val) * 0.3048 * 0.01
        if mode == Mode.HEADING:
            val = match.group('val')
            arg = int(val)
        if mode == Mode.POSITION:
            arg = LOCATIONS_NED.get(arg) if ned else LOCATIONS_LAT_LON.get(arg)
        if mode == Mode.LAND:
            arg = ' '.join([match.group('val'), match.group('unit')])
            arg = LOCATIONS_NED.get(arg) if ned else LOCATIONS_LAT_LON.get(arg)
        return arg


class MissionPlanner(Vocabulary):
    def __init__(self, drone: System):
        self.drone = drone
        self.mission_plan = None
        self.target_alt = 5

    @staticmethod
    async def try_action(action_coro, error):
        try:
            await action_coro()
        except error as e:
            logging.error(e)
            logging.debug(traceback.format_exc())
        await asyncio.sleep(0.1)

    def fetch_command_coro(self, mode: Mode, *args):
        if mode == Mode.ALTITUDE:
            return self.mission_change_altitude(*args)
        if mode == Mode.POSITION:
            return self.mission_fly_direct(*args)
        if mode == Mode.HEADING:
            return self.mission_fly_heading(*args)
        if mode == Mode.TAKEOFF:
            return self.command_takeoff()
        if mode == Mode.LAND:
            return self.command_landing(*args)

    async def get_position(self) -> telemetry.Position:
        async for position in self.drone.telemetry.position():
            if not position:
                await asyncio.sleep(0.1)
            return position

    async def upload_and_start(self, mission_plan):
        await self.drone.mission.clear_mission()
        await self.drone.mission.upload_mission(mission_plan)
        logging.debug("Mission:" + "".join(map(
            lambda item: f"\n\t{item.latitude_deg}, {item.longitude_deg}, {item.relative_altitude_m}",
            mission_plan.mission_items)))
        async for mission_progress in self.drone.mission.mission_progress():
            logging.debug(mission_progress)
            break
        await self.try_action(self.drone.mission.start_mission, mission.MissionError)
        await asyncio.sleep(0.1)

    async def mission_change_altitude(self, target_alt: float):
        logging.info(f"Change target altitude to {target_alt}m ASL")
        self.target_alt = target_alt
        if self.mission_plan is not None:
            items = list()
            for item in self.mission_plan.mission_items:
                items.append(mission.MissionItem(
                    item.latitude_deg, item.longitude_deg, self.target_alt,
                    item.speed_m_s, item.is_fly_through, item.gimbal_pitch_deg, item.gimbal_yaw_deg,
                    item.camera_action, item.loiter_time_s, item.camera_photo_interval_s
                ))
            self.mission_plan = mission.MissionPlan(items)
        else:
            pos = await self.get_position()
            items = [mission.MissionItem(
                pos.latitude_deg, pos.longitude_deg, self.target_alt,
                1.0, False, float('nan'), float('nan'),
                mission.MissionItem.CameraAction.NONE,
                5.0, float('nan')
            )]
            self.mission_plan = mission.MissionPlan(items)
        await self.upload_and_start(self.mission_plan)

    async def mission_fly_heading(self, heading: int):
        logging.info(f"Turning to {heading}")
        pos_gps = await self.get_position()
        pos_utm = utm.from_latlon(pos_gps.latitude_deg, pos_gps.longitude_deg)
        tgt_utm = (pos_utm[0] + math.sin(math.radians(heading)) * 5, pos_utm[1] + math.cos(math.radians(heading)) * 5)
        tgt_gps = utm.to_latlon(*tgt_utm, pos_utm[2], pos_utm[3])
        items = [mission.MissionItem(
            *tgt_gps, self.target_alt,
            1.0, False, float('nan'), float('nan'),
            mission.MissionItem.CameraAction.NONE,
            5.0, float('nan')
        )]
        self.mission_plan = mission.MissionPlan(items)
        await self.upload_and_start(self.mission_plan)

    async def mission_fly_direct(self, position: telemetry.Position):
        logging.info(f"Set enroute towards {position.latitude_deg}, {position.longitude_deg}")
        pos_gps = await self.get_position()
        items = [mission.MissionItem(
            position.latitude_deg, position.longitude_deg, self.target_alt,
            1.0, False, float('nan'), float('nan'),
            mission.MissionItem.CameraAction.NONE,
            5.0, float('nan')
        )]
        self.mission_plan = mission.MissionPlan(items)
        await self.upload_and_start(self.mission_plan)

    async def command_takeoff(self):
        logging.info("Arming drone")
        await self.try_action(self.drone.action.arm, action.ActionError)
        await asyncio.wait_for(self.is_armed(), timeout=10)
        logging.info("Taking off")
        await self.try_action(self.drone.action.takeoff, action.ActionError)
        await asyncio.sleep(5)
        await asyncio.wait_for(self.is_airborne(), timeout=10)
        await asyncio.sleep(1)

    async def command_landing(self, position=None):
        logging.info(f"Inbound for landing at {position.latitude_deg}, {position.longitude_deg}")
        await asyncio.sleep(0.1)
        if position is not None:
            items = [
                mission.MissionItem(
                    position.latitude_deg, position.longitude_deg, 5.0,
                    1.0, False, float('nan'), float('nan'),
                    mission.MissionItem.CameraAction.NONE,
                    5.0, float('nan')),
                mission.MissionItem(
                    position.latitude_deg, position.longitude_deg, 1.0,
                    1.0, False, float('nan'), float('nan'),
                    mission.MissionItem.CameraAction.NONE,
                    5.0, float('nan'))
            ]
            self.mission_plan = mission.MissionPlan(items)
            await self.upload_and_start(self.mission_plan)
            async for progress in self.drone.mission.mission_progress():
                if progress:
                    logging.debug(progress)
                    break
                await asyncio.sleep(0.1)
            await self.drone.mission.is_mission_finished()
        await asyncio.sleep(5)
        logging.info(f"Starting final descent")
        await self.try_action(self.drone.action.land, action.ActionError)
        await asyncio.wait_for(self.is_landed(), timeout=30)
        await asyncio.sleep(1)
        logging.info("Disarming drone")
        await self.try_action(self.drone.action.disarm, action.ActionError)
        await asyncio.wait_for(self.is_disarmed(), timeout=10)
        await asyncio.sleep(1)

    async def is_armed(self):
        async for armed in self.drone.telemetry.armed():
            if armed:
                logging.info("Arming successful")
                return True
            await asyncio.sleep(0.1)

    async def is_disarmed(self):
        async for armed in self.drone.telemetry.armed():
            if not armed:
                logging.info("Disarming successful")
                return True
            await asyncio.sleep(0.1)
            logging.debug("Waiting...")

    async def is_airborne(self):
        async for in_air in self.drone.telemetry.in_air():
            if in_air:
                logging.info("Takeoff successful")
                return True
            await asyncio.sleep(0.1)

    async def is_landed(self):
        async for landed_state in self.drone.telemetry.landed_state():
            if landed_state == telemetry.LandedState.ON_GROUND:
                logging.info("Landing successful")
                return True
            await asyncio.sleep(0.1)
