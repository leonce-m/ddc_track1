import sys
import signal
import logging
import asyncio
from mavsdk import System
from mavsdk.telemetry import *
from mavsdk.action import *
from mavsdk.offboard import *
from concurrent.futures import ThreadPoolExecutor
from dev import vio, misc


class ControlError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return f"{type(self).__name__}: {self.message}"


class VCS:
    def __init__(self, drone: System, call_sign: str, serial: str):
        self.listen = True
        self.drone = drone
        self.system_address = serial
        self.command_parser = vio.Parser(call_sign)
        self.abort_event = asyncio.Event()
        self.command_queue = asyncio.Queue()
        self.tp_executor = ThreadPoolExecutor()

    async def startup(self):
        await self.drone.connect(system_address=self.system_address)
        logging.info(f"{self.system_address} waiting for connection")
        async for state in self.drone.core.connection_state():
            if state.is_connected:
                logging.info(f"Connected to {self.system_address}")
                break
            await asyncio.sleep(0.1)
        logging.info("Setting mission params")
        await self.drone.action.set_takeoff_altitude(2)
        await self.drone.action.set_return_to_launch_altitude(2)
        logging.info("Arming drone")
        async for armed in self.drone.telemetry.armed():
            if armed:
                logging.info("Arming complete")
                break
            else:
                await self.drone.action.arm()
            await asyncio.sleep(0.1)

    # noinspection PyBroadException
    async def run(self):
        try:
            logging.info("Initializing")
            await self.startup()
            await asyncio.sleep(1)
            logging.info("Starting main routine")
            await asyncio.gather(
                self.monitor_atc(),
                self.monitor_telem(),
                self.monitor_health(),
                self.fly_commands()
            )
        except (KeyboardInterrupt, ControlError, ActionError, TelemetryError, OffboardError) as e:
            logging.error(e)
            self.abort_event.set()
            await self.fly_rtb()
            asyncio.create_task(self.shutdown(asyncio.get_running_loop()))

    async def monitor_atc(self):
        logging.info("Monitoring ATC")
        while not self.abort_event.is_set():
            meta = await asyncio.get_event_loop().run_in_executor(self.tp_executor, self.handle_stdin)
            if meta:
                await self.command_queue.put(meta)

    def handle_stdin(self):
        command = sys.stdin.readline().rstrip()
        if command == "rtb":
            raise ControlError("Received RTB command input")
        return self.command_parser.handle_command(command)

    async def monitor_telem(self):
        logging.info("Monitoring State")
        async for telem in self.drone.telemetry.position():
            # logging.info(telem)
            if self.abort_event.is_set():
                break
            await asyncio.sleep(1)

    async def monitor_health(self):
        logging.info("Monitoring Health")
        while not self.abort_event.is_set():
            await asyncio.sleep(1)
            # await asyncio.sleep(60)
            # raise ControlError("Drone system issue encountered")

    async def fly_commands(self):
        logging.info("Following ATC command queue")
        await self.drone.action.takeoff()

        while not self.abort_event.is_set():
            command_batch = await self.command_queue.get()
            logging.debug(f"Interpreting {command_batch}")
            # TODO: interpret command (mode, arg)

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
        logging.exception(f"Caught exception: {msg}")
        asyncio.create_task(self.shutdown(loop))

    # noinspection PyBroadException, PyProtectedMember
    async def shutdown(self, loop, sig=None):
        self.abort_event.set()
        if sig:
            logging.info(f"Received exit signal {sig.name}...")
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        [task.cancel() for task in tasks]
        logging.debug("Shutting down executor")
        self.tp_executor.shutdown(wait=False)
        logging.debug(f"Releasing {len(self.tp_executor._threads)} threads from executor")
        for thread in self.tp_executor._threads:
            try:
                thread._tstate_lock.release()
            except Exception:
                pass
        logging.debug(f"Cancelling {len(tasks)} outstanding tasks")
        await asyncio.gather(*tasks, return_exceptions=True)
        logging.debug(f"Flushing metrics")
        await asyncio.sleep(1)
        loop.stop()


def main(args):
    vcs = VCS(System(), args.call_sign, args.serial)
    loop = asyncio.get_event_loop()
    signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
    for s in signals:
        loop.add_signal_handler(s, lambda sig=s: asyncio.create_task(vcs.shutdown(loop, sig)))
    loop.set_exception_handler(vcs.handle_exception)

    try:
        loop.create_task(vcs.run())
        loop.run_forever()
    finally:
        loop.close()
        logging.info("Successfully shutdown VCS")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Control PIXHAWK via MavSDK-Python with ATC commands (and respond)")
    parser.add_argument('-c', '--call_sign', default="CityAirbus1234",
                        help="Set custom call sign")
    parser.add_argument('-s', '--serial', default="udp://:14550",
                        help="Set system address for drone serial port connection")
    parser.add_argument('-v', '--verbose', action='store_true',
                        help="Set logging level to DEBUG")
    ARGS = parser.parse_args()
    misc.config_logging_stdout(logging.DEBUG if ARGS.verbose else logging.INFO)
    main(ARGS)
