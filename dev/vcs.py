import sys
import logging
import signal
import asyncio
import concurrent.futures
from mavsdk import System
from mavsdk.telemetry import *
from concurrent.futures import ThreadPoolExecutor
from dev import vio, misc


class VCS:
    def __init__(self, drone, call_sign, serial):
        self.listen = True
        self.drone = drone
        self.system_address = serial
        self.command_parser = vio.Parser(call_sign)
        self.abort_event = asyncio.Event()
        self.command_queue = asyncio.Queue()

    async def startup(self):
        logging.info("Initializing")
        await self.drone.connect(system_address=self.system_address)
        logging.info(f"{self.system_address} waiting for connection")
        async for state in self.drone.core.connection_state():
            if state.is_connected:
                logging.info(f"Connected to {self.system_address}")
                break

        logging.info("Arming drone")
        async for armed in self.drone.telemetry.armed():
            if armed:
                logging.info("Arming complete")
                break
            else:
                await self.drone.action.arm()
                await asyncio.sleep(0.1)
        await asyncio.sleep(1)
        logging.info("Starting main routine")
        asyncio.create_task(self.run())

    async def run(self):
        results = await asyncio.gather(
            self.monitor_atc(),
            self.monitor_telem(),
            self.monitor_health(),
            self.fly_commands()
        )
        await self.handle_emergency(results)

    async def monitor_atc(self, prompt: str = ""):
        logging.info("Monitoring ATC")
        if not self.listen:
            return
        while not self.abort_event.is_set():
            # TODO: listen to stdio and call command_parser.handle_command(string)
            # TODO: append return of handle_command to command_queue
            await asyncio.sleep(1)
        # with ThreadPoolExecutor(1, "AsyncInput", lambda x: print(x, end="", flush=True), (prompt,)) as executor:
        # return (await asyncio.get_event_loop().run_in_executor(executor, sys.stdin.readline)).rstrip()

    async def monitor_telem(self):
        logging.info("Monitoring State")
        while not self.abort_event.is_set():
            await asyncio.sleep(1)

    async def monitor_health(self):
        logging.info("Monitoring Health")
        while not self.abort_event.is_set():
            await asyncio.sleep(1)

    async def fly_commands(self):
        logging.info("Following ATC command queue")
        await self.drone.action.takeoff()

        while not self.abort_event.is_set():
            command, *args = await self.command_queue.get()
            logging.info(f"Calling {command}({args})")
            await command(args)
        await self.fly_rtb()

    async def handle_emergency(self, results):
        logging.info("Attempt to recover from error")
        for emergency in results:
            if isinstance(emergency, Exception):
                raise emergency
        await self.fly_rtb()
        await self.shutdown(asyncio.get_running_loop())

    async def fly_rtb(self):
        logging.info("Attempt to land at nearest location")
        await self.drone.action.return_to_launch()
        logging.info("Returning Home")
        async for landed in self.drone.telemetry.landed_state():
            if landed == LandedState.ON_GROUND:
                logging.info("Landed")
                break
        await asyncio.sleep(1)
        logging.info("Disarming drone")
        await self.drone.action.disarm()

    def handle_exception(self, loop, context):
        msg = context.get("exception", context["message"])
        logging.error(f"Caught exception: {msg}")
        logging.info("Shutting down")
        self.abort_event.set()
        asyncio.create_task(self.shutdown(loop))

    async def shutdown(self, loop, sig=None):
        if sig:
            logging.info(f"Received exit signal {sig.name}...")
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        [task.cancel() for task in tasks]

        logging.info(f"Cancelling {len(tasks)} outstanding tasks")
        await asyncio.gather(*tasks, return_exceptions=True)
        logging.info(f"Flushing metrics")
        loop.stop()


async def make_async(sync_function):
    executor = concurrent.futures.ThreadPoolExecutor()
    return await asyncio.get_event_loop().run_in_executor(executor, sync_function)


def main(args):
    vcs = VCS(System(), args.call_sign, args.serial)
    loop = asyncio.get_event_loop()
    signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
    for s in signals:
        loop.add_signal_handler(s, lambda sig=s: asyncio.create_task(vcs.shutdown(sig, loop)))
    loop.set_exception_handler(vcs.handle_exception)

    try:
        loop.create_task(vcs.startup())
        loop.run_forever()
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
        logging.info("Successfully shutdown VCS")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Control PIXHAWK via MavSDK-Python with ATC commands (and respond)")
    parser.add_argument('-c', '--call_sign', default="CityAirbus1234",
                        help="Set custom call sign")
    parser.add_argument('-s', '--serial', default="udp://:14550",
                        help="Set system address for drone serial port connection")
    ARGS = parser.parse_args()

    misc.config_logger()
    main(ARGS)
