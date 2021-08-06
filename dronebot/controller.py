import asyncio
import logging
import signal
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor

from mavsdk import System, telemetry, action, mission

from dronebot import config_logging
from dronebot.parser import Parser
from dronebot.state import FlightState
from dronebot.telem import Telemetry

logger = logging.getLogger(__name__.upper())


class ControlError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return f"{type(self).__name__}: {self.message}"


class Controller:
    """
    Handling mavsdk based asynchronous communication from a companion computer to a drone flight controller.
    * sets up a udp/tcp/serial connection
    * starts the stdin deepspeech parser in a separate thread
    * converts the parsed input queue into callable dommands containing mavskd flight instructions
    * watches flight parameters
    * safely handles exeptions and interrupts
    """

    def __init__(self, drone: System, call_sign: str, serial: str, restore: bool):
        self.drone = drone
        self.system_address = serial

        self.abort_event = asyncio.Event()
        self.command_queue = asyncio.Queue()
        self.tp_executor = ThreadPoolExecutor()

        self.parser = Parser(call_sign)
        self.flight_state = FlightState(self.command_queue, restore)
        self.telemetry = Telemetry(self.drone)

    async def startup(self):
        await self.drone.connect(system_address=self.system_address)
        logger.info(f"{self.system_address} waiting for connection...")
        async for state in self.drone.core.connection_state():
            if state.is_connected:
                logger.info(f"Connected to {self.system_address}")
                break
            await asyncio.sleep(0.1)
        logger.info("Running preflight checklist...")
        n_tries = 0
        async for health_all_ok in self.drone.telemetry.health_all_ok():
            if n_tries == 5:
                raise ControlError("Preflight check maximum tries exceeded")
            if health_all_ok:
                logger.info("Preflight checklist complete")
                break
            else:
                logger.info(f"Preflight check failed {n_tries}/5")
                async for health in self.drone.telemetry.health():
                    logger.debug(str(health).replace(' [', '\n\t').replace(', ', '\n\t').replace(']', ''))
                    break
                n_tries += 1
                await asyncio.sleep(5)
        logger.info("Setting mission params")
        await self.drone.action.set_takeoff_altitude(5)
        await self.drone.action.set_return_to_launch_altitude(20)

    # noinspection PyBroadException
    async def run(self):
        try:
            logger.info("Initializing")
            await self.startup()
            await asyncio.sleep(1)
            logger.info("Starting main routine")
            while not self.abort_event.is_set():
                try:
                    await asyncio.gather(
                        self.monitor_atc(),
                        self.monitor_health(),
                        self.telemetry.sub_state_updates(),
                        self.telemetry.sub_position_updates(),
                        self.fly_commands()
                    )
                except (action.ActionError, telemetry.TelemetryError, mission.MissionError) as e:
                    logger.exception(e)
                    logger.debug(traceback.format_exc())
        except Exception as e:
            logger.exception(e)
            logger.debug(traceback.format_exc())
            self.abort_event.set()
            await self.fly_rtb()
            asyncio.create_task(self.shutdown(asyncio.get_running_loop()))

    async def monitor_atc(self):
        await self.flight_state.voice.speak(full=True)
        await asyncio.sleep(1)
        await self.flight_state.voice.speak("request IFR clearance")
        logger.info("Monitoring ATC")
        while not self.abort_event.is_set():
            command_list = await asyncio.get_event_loop().run_in_executor(self.tp_executor, self.handle_stdin)
            await self.flight_state.handle_commands(command_list)
            await self.flight_state.voice.speak()

    def handle_stdin(self):
        command = sys.stdin.readline().rstrip()
        if command == "rtb":
            raise ControlError("Received RTB command input")
        return self.parser.handle_command(command)

    async def monitor_health(self):
        logger.info("Monitoring Health")
        trigger_state = True
        async for health_ok in self.drone.telemetry.health_all_ok():
            if self.abort_event.is_set():
                break
            if not health_ok and trigger_state:
                logger.warning("Drone health issue encountered")
                await self.telemetry.print_telem_status()
                trigger_state = False
            if health_ok:
                trigger_state = True
            await asyncio.sleep(1)

    async def fly_commands(self):
        logger.info("Following ATC command queue")
        while not self.abort_event.is_set():
            command = await self.command_queue.get()
            logger.debug(f"Interpreting {command}")
            task = command(self.drone, self.telemetry)
            asyncio.create_task(task)

    async def fly_rtb(self):
        logger.info("Attempt to land at nearest location")
        await self.drone.action.return_to_launch()
        logger.info("Returning Home")
        await self.telemetry.is_landed()
        logger.info("Landed")
        await asyncio.sleep(1)
        logger.info("Disarming drone")
        await self.drone.action.disarm()

    def handle_exception(self, loop, context):
        msg = context.get("exception", context["message"])
        logger.exception(f"Caught exception: {msg}")
        logger.debug(traceback.format_exc())
        asyncio.create_task(self.shutdown(loop))

    # noinspection PyBroadException, PyProtectedMember
    async def shutdown(self, loop, sig=None):
        self.abort_event.set()
        if sig:
            logger.info(f"Received exit signal {sig.name}...")
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        [task.cancel() for task in tasks]
        logger.debug("Shutting down executor")
        self.tp_executor.shutdown(wait=False)
        logger.debug(f"Releasing {len(self.tp_executor._threads)} threads from executor")
        for thread in self.tp_executor._threads:
            try:
                thread._tstate_lock.release()
            except Exception:
                pass
        logger.debug(f"Cancelling {len(tasks)} outstanding tasks")
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.debug(f"Flushing metrics")
        await asyncio.sleep(1)
        loop.stop()
        self.flight_state.save()


def main(args):
    vcs = Controller(System(), args.call_sign, args.serial, args.restore)
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
    parser.add_argument('-c', '--call_sign', default="cityairbus1234",
                        help="Set custom call sign")
    parser.add_argument('-s', '--serial', default="udp://:14550",
                        help="Set system address for drone serial port connection")
    parser.add_argument('-v', '--verbose', action='store_true',
                        help="Set logging level to DEBUG")
    parser.add_argument('-r', '--restore', action='store_true',
                        help="Restore flight state machine from an earlier state")
    ARGS = parser.parse_args()
    config_logging.config_logging_stdout(logging.DEBUG if ARGS.verbose else logging.INFO, full=True)
    # from dronebot import test_commands
    # test_commands.run()
    main(ARGS)
