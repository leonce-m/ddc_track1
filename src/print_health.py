import asyncio
import logging
import re
from mavsdk import System, telemetry
import misc

misc.config_logging_stdout(logging.DEBUG)

async def print_telem_status(drone):
    async for is_armed in drone.telemetry.armed():
        logging.debug(f"Armed state:\n\t{is_armed}")
        break
    async for flight_mode in drone.telemetry.flight_mode():
        logging.debug(f"Flight mode:\n\t{flight_mode}")
        break
    async for landed_state in drone.telemetry.landed_state():
        logging.debug(f"Landed State:\n\t{landed_state}")
        break
    async for battery in drone.telemetry.battery():
        logging.debug(str(battery).replace(' [', '\n\t').replace(', ', '\n\t').replace(']', ''))
        break
    async for gps_info in drone.telemetry.gps_info():
        logging.debug(str(gps_info).replace(' [', '\n\t').replace(', ', '\n\t').replace(']', ''))
        break
    async for health in drone.telemetry.health():
        logging.debug(str(health).replace(' [', '\n\t').replace(', ', '\n\t').replace(']', ''))
        break
    async for position in drone.telemetry.position():
        logging.debug(str(position).replace(' [', '\n\t').replace(', ', '\n\t').replace(']', ''))
        break

async def run():
    drone_handle = System()
    await drone_handle.connect(system_address="udp://:14540")
    await print_telem_status(drone_handle)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())
