import asyncio
import concurrent.futures
from mavsdk import System


async def make_async(self, sync_function):
    executor = concurrent.futures.ThreadPoolExecutor()
    await loop.run_in_executor(executor, sync_function)


class VCS:
    def __init__(self, drone):
        self.drone = drone

    def get_message(self):
        command = input()
        token = command.split()


async def run(self):
    drone = System()
    vcs = VCS(drone)
    await drone.connect(system_address="udp://:14540")
    async for state in drone.core.connection_state():
        if state.is_connected:
            break
    await make_async(self.get_message())
    await drone.action.arm()
    await drone.action.takeoff()


if __name__ == "__main__":
    asyncio.ensure_future(run())
    asyncio.get_event_loop().run_forever()
