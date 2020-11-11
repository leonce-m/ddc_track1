import sys
import logging
import signal
import asyncio
import concurrent.futures
from mavsdk import System
import mavsdk.telemetry
from concurrent.futures import ThreadPoolExecutor

class VCS:
    def __init__(self, drone):
        self.listen = True
        self.drone = drone
        self.command_queue = asyncio.Queue()

    async def startup(self):
        logging.info("Initializing")
        system_address = "udp://:14550"
        await self.drone.connect(system_address=system_address)
        logging.info(f"{system_address} waiting for connection")
        async for state in self.drone.core.connection_state():
            if state.is_connected:
                logging.info(f"Connected to {system_address}")
                break

        logging.info("Arming drone")
        async for state in self.drone.telemetry.armed():
            if state.is_armed:
                logging.info("Arming complete")
                break
            else:
                await self.drone.action.arm()
                await asyncio.sleep(0.1)
        await asyncio.sleep(1)

        logging.info("Starting main coroutines")
        asyncio.create_task(self.monitor_atc())
        asyncio.create_task(self.monitor_telem())
        asyncio.create_task(self.monitor_health())
        asyncio.create_task(self.fly_commands())

    async def handle_command(self, command):
        logging.info("Command received: " + command)

    async def monitor_atc(self, prompt: str = ""):
        logging.info("Monitoring ATC")
        if not self.listen:
            return
        with ThreadPoolExecutor(1, "AsyncInput", lambda x: print(x, end="", flush=True), (prompt,)) as executor:
            return (await asyncio.get_event_loop().run_in_executor(executor, sys.stdin.readline)).rstrip()

    async def monitor_telem(self):
        logging.info("Monitoring State")
        while True:
            await asyncio.sleep(1)

    async def monitor_health(self):
        logging.info("Monitoring Health")
        while True:
            await asyncio.sleep(1)

    async def fly_commands(self):
        while True:
            command, *args = await self.command_queue.get()
            logging.info(f"Exec drone.{command}({args})")

    async def recover(self, loop, context):
        logging.info("Attempt to recover from error")

        msg = context.get("exception", context["message"])
        logging.error(f"Caught exception: {msg}")
        logging.info("Shutting down...")
        asyncio.create_task(self.shutdown(loop))

    async def fly_emergency(self):
        logging.info("Attempt to land at nearest location")

    async def shutdown(self, loop, signal=None):
        if signal:
            logging.info(f"Received exit signal {signal.name}...")
        logging.info("Attempt in position landing")
        logging.info("Disarming drone")
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        [task.cancel() for task in tasks]

        logging.info(f"Cancelling {len(tasks)} outstanding tasks")
        await asyncio.gather(*tasks, return_exceptions=True)
        logging.info(f"Flushing metrics")
        loop.stop()


async def make_async(sync_function):
    executor = concurrent.futures.ThreadPoolExecutor()
    return await asyncio.get_event_loop().run_in_executor(executor, sync_function)


if __name__ == "__main__":
    vcs = VCS(System())
    loop = asyncio.get_event_loop()
    signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
    for s in signals:
        loop.add_signal_handler(s, lambda sig=s: asyncio.create_task(vcs.recover(sig, loop)))
    loop.set_exception_handler(vcs.recover)

    try:
        loop.create_task(vcs.startup())
        loop.run_forever()
    finally:
        loop.close()
        logging.info("Successfully shutdown VCS")
