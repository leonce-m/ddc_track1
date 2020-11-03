import asyncio
import concurrent.futures
from mavsdk import System


class VCS:
    def __init__(self, drone):
        self.debug = True
        self.drone = drone

    def print(self, message):
        if self.debug:
            print(message)

    async def startup(self):
        self.print("Initializing...")
        system_address = "udp://:14550"
        await self.drone.connect(system_address=system_address)
        self.print(f"{system_address} waiting for connection...")
        async for state in self.drone.core.connection_state():
            self.print("...")
            await asyncio.sleep(1)
            if state.is_connected:
                self.print(f"Connected to {system_address}!")
                break
        self.print("Arming drone...")
        await self.drone.action.arm()

    async def main_loop(self):
        await self.handle_state()
        command = await make_async(input)
        await self.handle_command(command)
        await asyncio.sleep(1)

    async def handle_state(self):
        self.print("Handling state...")

    async def handle_command(self, command):
        self.print("Command received: " + command)


async def make_async(sync_function):
    executor = concurrent.futures.ThreadPoolExecutor()
    return await asyncio.get_event_loop().run_in_executor(executor, sync_function)


if __name__ == "__main__":
    vcs = VCS(System())
    asyncio.get_event_loop().run_until_complete(vcs.startup())
    asyncio.ensure_future(vcs.main_loop())
    asyncio.get_event_loop().run_forever()
