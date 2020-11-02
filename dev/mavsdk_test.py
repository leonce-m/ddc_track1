import asyncio
import concurrent.futures
from mavsdk import System


def get_message():
    return input()


async def make_async(sync_function):
    executor = concurrent.futures.ThreadPoolExecutor()
    await loop.run_in_executor(executor, sync_function)


async def run():
    drone = System()
    await drone.connect(system_address="udp://:14540")
    async for state in drone.core.connection_state():
        if state.is_connected:
            break
    await make_async(get_message())
    await drone.action.arm()
    await drone.action.takeoff()
    await asyncio.sleep(5)
    await drone.action.land()


if __name__ == "__main__":
    asyncio.ensure_future(run())
    asyncio.get_event_loop().run_forever()