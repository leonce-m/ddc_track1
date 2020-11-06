import sys
import asyncio
import concurrent.futures
from mavsdk import System
from concurrent.futures import ThreadPoolExecutor

class VCS:
    def __init__(self, drone):
        self.verbose = True
        self.listen = True
        self.drone = drone

    async def ainput(self, prompt: str = ""):
        if not self.listen:
            return
        with ThreadPoolExecutor(1, "AsyncInput", lambda x: print(x, end="", flush=True), (prompt,)) as executor:
            return (await asyncio.get_event_loop().run_in_executor(
                executor, sys.stdin.readline
            )).rstrip()

    async def aprint(self, message):
        if self.verbose:
            print(message)

    async def start(self):
        await self.aprint("Initializing...")
        system_address = "udp://:14550"
        await self.drone.connect(system_address=system_address)
        await self.aprint(f"{system_address} waiting for connection...")
        async for state in self.drone.core.connection_state():
            await self.aprint("...")
            await asyncio.sleep(1)
            if state.is_connected:
                await self.aprint(f"Connected to {system_address}!")
                break
        await self.aprint("Arming drone...")
        await self.drone.action.arm()

    async def run(self):
        await self.handle_state()
        command = await self.ainput()
        await self.handle_command(command)
        await asyncio.sleep(1)

    async def handle_state(self):
        await self.aprint("Handling state...")

    async def handle_command(self, command):
        await self.aprint("Command received: " + command)


async def make_async(sync_function):
    executor = concurrent.futures.ThreadPoolExecutor()
    return await asyncio.get_event_loop().run_in_executor(executor, sync_function)


if __name__ == "__main__":
    vcs = VCS(System())
    loop = asyncio.get_event_loop()
    loop.run_until_complete(vcs.start())
    asyncio.ensure_future(vcs.run())
    loop.run_forever()
    loop.close()
