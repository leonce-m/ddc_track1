import asyncio
import logging
import math
import traceback

import utm
from mavsdk import System, telemetry, action, mission
from dronebot.vocab import Vocabulary

logger = logging.getLogger(__name__.upper())

class MissionPlanner:
    """
    Provides mavsdk coroutines based on parsed command input.
    """

    def __init__(self, drone: System):
        super().__init__()
        self.drone = drone
        self.mission_plan = None
        self.vocab = Vocabulary()
        self.target_alt = 5

    @staticmethod
    async def try_action(action_coro, error):
        try:
            await action_coro()
        except error as e:
            logger.error(e)
            logger.debug(traceback.format_exc())
        await asyncio.sleep(0.1)

    def fetch_command_coro(self, mode, *args):
        if mode == self.vocab.MODE.ALTITUDE:
            return self.mission_change_altitude(*args)
        if mode == self.vocab.MODE.POSITION:
            return self.mission_fly_direct(*args)
        if mode == self.vocab.MODE.HEADING:
            return self.mission_fly_heading(*args)
        if mode == self.vocab.MODE.TAKEOFF:
            return self.command_takeoff()
        if mode == self.vocab.MODE.LAND:
            return self.command_landing(*args)

    async def get_position(self) -> telemetry.Position:
        async for position in self.drone.telemetry.position():
            if not position:
                await asyncio.sleep(0.1)
            return position

    async def upload_and_start(self, mission_plan):
        await self.drone.mission.clear_mission()
        await self.drone.mission.upload_mission(mission_plan)
        logger.debug("Mission:" + "".join(map(
            lambda item: f"\n\t{item.latitude_deg}, {item.longitude_deg}, {item.relative_altitude_m}",
            mission_plan.mission_items)))
        async for mission_progress in self.drone.mission.mission_progress():
            logger.debug(mission_progress)
            break
        await self.try_action(self.drone.mission.start_mission, mission.MissionError)
        await asyncio.sleep(0.1)

    async def mission_change_altitude(self, target_alt: float):
        logger.info(f"Change target altitude to {target_alt}m ASL")
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
        logger.info(f"Turning to {heading}")
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
        logger.info(f"Set enroute towards {position.latitude_deg}, {position.longitude_deg}")
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
        logger.info("Arming drone")
        await self.try_action(self.drone.action.arm, action.ActionError)
        await asyncio.wait_for(self.is_armed(), timeout=10)
        logger.info("Taking off")
        await self.try_action(self.drone.action.takeoff, action.ActionError)
        await asyncio.sleep(5)
        await asyncio.wait_for(self.is_airborne(), timeout=10)
        await asyncio.sleep(1)

    async def command_landing(self, position=None):
        logger.info(f"Inbound for landing at {position.latitude_deg}, {position.longitude_deg}")
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
                    logger.debug(progress)
                    break
                await asyncio.sleep(0.1)
            await self.drone.mission.is_mission_finished()
        await asyncio.sleep(5)
        logger.info(f"Starting final descent")
        await self.try_action(self.drone.action.land, action.ActionError)
        await asyncio.wait_for(self.is_landed(), timeout=30)
        await asyncio.sleep(1)
        logger.info("Disarming drone")
        await self.try_action(self.drone.action.disarm, action.ActionError)
        await asyncio.wait_for(self.is_disarmed(), timeout=10)
        await asyncio.sleep(1)

    async def is_armed(self):
        async for armed in self.drone.telemetry.armed():
            if armed:
                logger.info("Arming successful")
                return True
            await asyncio.sleep(0.1)

    async def is_disarmed(self):
        async for armed in self.drone.telemetry.armed():
            if not armed:
                logger.info("Disarming successful")
                return True
            await asyncio.sleep(0.1)
            logger.debug("Waiting...")

    async def is_airborne(self):
        async for in_air in self.drone.telemetry.in_air():
            if in_air:
                logger.info("Takeoff successful")
                return True
            await asyncio.sleep(0.1)

    async def is_landed(self):
        async for landed_state in self.drone.telemetry.landed_state():
            if landed_state == telemetry.LandedState.ON_GROUND:
                logger.info("Landing successful")
                return True
            await asyncio.sleep(0.1)
