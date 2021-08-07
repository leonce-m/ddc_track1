import asyncio
import logging
import math
import time
import traceback
from abc import abstractmethod, ABCMeta

import numpy as np
import utm
from mavsdk import System, action, mission

from dronebot.telem import Telemetry

logger = logging.getLogger(__name__.upper())


class BaseCommand(object, metaclass=ABCMeta):
    def __init__(self):
        super().__init__()
        self.time_stamp = time.time()

    @abstractmethod
    async def __call__(self, drone: System, telem: Telemetry):
        pass

    @abstractmethod
    def __str__(self):
        pass

    @staticmethod
    async def try_action(action_coro, error):
        try:
            await action_coro()
        except error as e:
            logger.error(e)
            logger.debug(traceback.format_exc())
        await asyncio.sleep(0.1)


class MoveCommand(BaseCommand, metaclass=ABCMeta):
    mission_plan = None
    altitude = 5

    def __init__(self):
        super().__init__()
        self.mission_plan = MoveCommand.mission_plan
        self.altitude = MoveCommand.altitude

    async def upload_and_start(self, drone, mission_plan):
        MoveCommand.mission_plan = mission_plan
        await drone.mission.clear_mission()
        await drone.mission.upload_mission(mission_plan)
        logger.debug("Mission:" + "".join(map(
            lambda item: f"\n\t{item.latitude_deg}, {item.longitude_deg}, {item.relative_altitude_m}",
            mission_plan.mission_items)))
        async for mission_progress in drone.mission.mission_progress():
            logger.debug(mission_progress)
            break
        await self.try_action(drone.mission.start_mission, mission.MissionError)
        await asyncio.sleep(0.1)

    def __str__(self):
        return f"{self.__class__.__name__} Command"


class Altitude(MoveCommand):
    def __init__(self, *, altitude):
        super().__init__()
        self.altitude = altitude

    async def __call__(self, drone, telem):
        logger.info(f"Change target altitude to {self.altitude}m ASL")
        MoveCommand.altitude = self.altitude
        if self.mission_plan is not None:
            items = list()
            for item in self.mission_plan.mission_items:
                items.append(mission.MissionItem(
                    item.latitude_deg, item.longitude_deg, self.altitude,
                    item.speed_m_s, item.is_fly_through, item.gimbal_pitch_deg, item.gimbal_yaw_deg,
                    item.camera_action, item.loiter_time_s, item.camera_photo_interval_s
                ))
            mission_plan = mission.MissionPlan(items)
        else:
            pos = telem.position
            items = [mission.MissionItem(
                pos.latitude_deg, pos.longitude_deg, self.altitude,
                1.0, False, float('nan'), float('nan'),
                mission.MissionItem.CameraAction.NONE,
                5.0, float('nan')
            )]
            mission_plan = mission.MissionPlan(items)
        await self.upload_and_start(drone, mission_plan)

class Heading(MoveCommand):
    def __init__(self, *, heading):
        super().__init__()
        self.heading = heading

    async def __call__(self, drone, telem):
        logger.info(f"Turning to {self.heading}")
        pos_gps = telem.position
        pos_utm = utm.from_latlon(pos_gps.latitude_deg, pos_gps.longitude_deg)
        tgt_utm = (pos_utm[0] + math.sin(math.radians(self.heading)) * 5, pos_utm[1] + math.cos(math.radians(self.heading)) * 5)
        tgt_gps = utm.to_latlon(*tgt_utm, pos_utm[2], pos_utm[3])
        items = [mission.MissionItem(
            *tgt_gps, self.altitude,
            1.0, False, float('nan'), float('nan'),
            mission.MissionItem.CameraAction.NONE,
            5.0, float('nan')
        )]
        await self.upload_and_start(drone, mission.MissionPlan(items))

class Direct(MoveCommand):
    def __init__(self, *, position):
        super().__init__()
        self.position = position

    async def __call__(self, drone, telem):
        logger.info(f"Set enroute towards {self.position.latitude_deg}, {self.position.longitude_deg}")
        items = [mission.MissionItem(
            self.position.latitude_deg, self.position.longitude_deg, self.altitude,
            1.0, False, float('nan'), float('nan'),
            mission.MissionItem.CameraAction.NONE,
            5.0, float('nan')
        )]
        await self.upload_and_start(drone, mission.MissionPlan(items))

class Takeoff(MoveCommand):
    def __init__(self, *, altitude=None):
        super().__init__()
        self.altitude = altitude

    async def __call__(self, drone, telem):
        if self.altitude:
            MoveCommand.altitude = self.altitude
            await drone.action.set_takeoff_altitude(self.altitude)
        while not telem.is_armed:
            await self.try_action(drone.action.arm, action.ActionError)
        await telem.wait_for_armed()
        while not telem.in_air:
            await self.try_action(drone.action.takeoff, action.ActionError)

class Land(MoveCommand):
    def __init__(self, *, position):
        super().__init__()
        self.position = position

    async def __call__(self, drone, telem):
        if self.position is not None:
            logger.info(f"Inbound for landing at {self.position.latitude_deg}, {self.position.longitude_deg}")
            items = [
                mission.MissionItem(
                    self.position.latitude_deg, self.position.longitude_deg, 5.0,
                    1.0, False, float('nan'), float('nan'),
                    mission.MissionItem.CameraAction.NONE,
                    5.0, float('nan')),
                mission.MissionItem(
                    self.position.latitude_deg, self.position.longitude_deg, 1.0,
                    1.0, False, float('nan'), float('nan'),
                    mission.MissionItem.CameraAction.NONE,
                    5.0, float('nan'))
            ]
            await self.upload_and_start(drone, mission.MissionPlan(items))
            async for progress in drone.mission.mission_progress():
                if progress:
                    logger.debug(progress)
                    break
                await asyncio.sleep(0.1)
            await drone.mission.is_mission_finished()
            logger.info("Starting final descent")
        else:
            logger.info("Landing at current position")
        await asyncio.sleep(5)
        await self.try_action(drone.action.land, action.ActionError)
        await asyncio.wait_for(telem.wait_for_landed(), timeout=30)
        await self.try_action(drone.action.disarm, action.ActionError)
        await asyncio.wait_for(telem.wait_for_disarmed(), timeout=10)

class ReportCommand(BaseCommand, metaclass=ABCMeta):
    def __init__(self, *, task):
        super().__init__()
        self.task = task

    def __str__(self):
        return f"{self.__class__.__name__} calling {self.task}"

class ReportPos(ReportCommand):
    def __init__(self, *, position, min_dist=2, task):
        super().__init__(task=task)
        self.position = np.array(utm.from_latlon(position.latitude_deg, position.longitude_deg)[0:2])
        self.min_dist = min_dist

    async def __call__(self, drone, telem):
        logger.debug(f"{self.task} waiting to reach {self.position}")
        while True:
            pos_utm = np.array(utm.from_latlon(telem.position.latitude_deg, telem.position.longitude_deg)[0:2])
            dist = np.linalg.norm(self.position - pos_utm)
            logger.debug(dist)
            if dist < self.min_dist:
                break
            await asyncio.sleep(1)
        logger.debug(self)
        await self.task

class ReportAlt(ReportCommand):
    def __init__(self, *, altitude, min_diff=0.5, task):
        super().__init__(task=task)
        self.altitude = altitude
        self.min_diff = min_diff

    async def __call__(self, drone, telem):
        logger.debug(f"{self.task} waiting to reach {self.altitude}m")
        while abs(self.altitude - telem.altitude) > self.min_diff:
            # logger.debug(telem.altitude)
            await asyncio.sleep(1)
        logger.debug(self)
        await self.task

class ReportTakeoff(ReportCommand):
    def __init__(self, *, task):
        super().__init__(task=task)

    async def __call__(self, drone, telem):
        logger.debug(f"{self.task} waiting for takeoff state")
        await telem.wait_for_in_air()
        logger.debug(self)
        await self.task

class ReportLanded(ReportCommand):
    def __init__(self, *, task):
        super().__init__(task=task)

    async def __call__(self, drone, telem):
        logger.debug(f"{self.task} waiting for landed state")
        await telem.wait_for_landed(1)
        logger.debug(self)
        await self.task


class EngineStart(BaseCommand):
    def __init__(self):
        super().__init__()

    async def __call__(self, drone, telem):
        logger.info("Engine Start (Armed)")
        await self.try_action(drone.action.arm, action.ActionError)

    def __str__(self):
        return f"{self.__class__.__name__} Command"


class EngineShutdown(BaseCommand):
    def __init__(self):
        super().__init__()

    async def __call__(self, drone, telem):
        logger.info("Engine Shutdown (Disarmed)")
        await self.try_action(drone.action.disarm, action.ActionError)

    def __str__(self):
        return f"{self.__class__.__name__} Command"

class Freestyle(BaseCommand):
    def __init__(self):
        super().__init__()

    async def __call__(self, drone, telem):
        logger.info("Doing a trick")

    def __str__(self):
        return f"{self.__class__.__name__} Command"
