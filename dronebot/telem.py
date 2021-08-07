import asyncio
import logging

from mavsdk import System, telemetry

logger = logging.getLogger(__name__.upper())

class Telemetry:
    def __init__(self, drone: System):
        self.drone = drone

        self.position = None
        self.altitude = None
        self.in_air = False
        self.is_armed = False
        self.is_landed = True

    async def sub_position_updates(self):
        await self.drone.telemetry.set_rate_position(10)
        async for position in self.drone.telemetry.position():
            self.position = position
            self.altitude = position.relative_altitude_m

    async def sub_state_updates(self):
        while True:
            async for armed in self.drone.telemetry.armed():
                self.is_armed = armed
                break
            async for in_air in self.drone.telemetry.in_air():
                self.in_air = in_air
                break
            async for landed_state in self.drone.telemetry.landed_state():
                self.is_landed = (landed_state == telemetry.LandedState.ON_GROUND)
                break
            await asyncio.sleep(1)

    async def wait_for_armed(self, rate=10):
        while not self.is_armed:
            await asyncio.sleep(1 / rate)
        return True

    async def wait_for_disarmed(self, rate=10):
        while self.is_armed:
            await asyncio.sleep(1 / rate)
        return True

    async def wait_for_in_air(self, rate=10):
        while not self.in_air:
            await asyncio.sleep(1 / rate)
        return True

    async def wait_for_landed(self, rate=10):
        while not self.is_landed:
            await asyncio.sleep(1 / rate)
        return True

    async def print_telem_status(self):
        async for is_armed in self.drone.telemetry.armed():
            logger.debug(f"Armed state:\n\t{is_armed}")
            break
        async for flight_mode in self.drone.telemetry.flight_mode():
            logger.debug(f"Flight mode:\n\t{flight_mode}")
            break
        async for landed_state in self.drone.telemetry.landed_state():
            logger.debug(f"Landed State:\n\t{landed_state}")
            break
        async for battery in self.drone.telemetry.battery():
            logger.debug(str(battery).replace(' [', '\n\t').replace(', ', '\n\t').replace(']', ''))
            break
        async for gps_info in self.drone.telemetry.gps_info():
            logger.debug(str(gps_info).replace(' [', '\n\t').replace(', ', '\n\t').replace(']', ''))
            break
        async for health in self.drone.telemetry.health():
            logger.debug(str(health).replace(' [', '\n\t').replace(', ', '\n\t').replace(']', ''))
            break
        async for position in self.drone.telemetry.position():
            logger.debug(str(position).replace(' [', '\n\t').replace(', ', '\n\t').replace(']', ''))
            break
