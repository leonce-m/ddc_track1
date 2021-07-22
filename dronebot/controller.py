import asyncio
import logging
import signal
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor

from mavsdk import System, telemetry, action, mission
from dronebot.mission_planner import MissionPlanner
from dronebot.stdin_parser import Parser
from dronebot.voice_response import TTS
from dronebot import config_logging


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
    * converts the parsed input queue into mavskd commands (through inherited methods from MissionPlanner)
    * watches flight parameters
    * safely handles exeptions and interrupts
    """

    def __init__(self, drone: System, call_sign: str, serial: str):
        self.drone = drone
        self.system_address = serial
        self.tts = TTS()
        self.parser = Parser(call_sign, self.tts)
        self.mission_planner = MissionPlanner(drone)
        self.abort_event = asyncio.Event()
        self.command_queue = asyncio.Queue()
        self.tp_executor = ThreadPoolExecutor()

    async def startup(self):
        await self.drone.connect(system_address=self.system_address)
        logging.info(f"{self.system_address} waiting for connection...")
        async for state in self.drone.core.connection_state():
            if state.is_connected:
                logging.info(f"Connected to {self.system_address}")
                break
            await asyncio.sleep(0.1)
        logging.info("Running preflight checklist...")
        n_tries = 0
        async for health_all_ok in self.drone.telemetry.health_all_ok():
            if n_tries == 5:
                raise ControlError("Preflight check maximum tries exceeded")
            if health_all_ok:
                logging.info("Preflight checklist complete")
                break
            else:
                logging.info(f"Preflight check failed {n_tries}/5")
                async for health in self.drone.telemetry.health():
                    logging.debug(str(health).replace(' [', '\n\t').replace(', ', '\n\t').replace(']', ''))
                    break
                n_tries += 1
                await asyncio.sleep(5)
        logging.info("Setting mission params")
        await self.drone.action.set_takeoff_altitude(5)
        await self.drone.action.set_return_to_launch_altitude(20)

    # noinspection PyBroadException
    async def run(self):
        try:
            logging.info("Initializing")
            await self.startup()
            await asyncio.sleep(1)
            logging.info("Starting main routine")
            while not self.abort_event.is_set():
                try:
                    await asyncio.gather(
                        self.monitor_atc(),
                        self.monitor_telem(),
                        self.monitor_health(),
                        self.fly_commands()
                    )
                except (action.ActionError, telemetry.TelemetryError, mission.MissionError) as e:
                    logging.exception(e)
        except Exception as e:
            logging.exception(e)
            self.abort_event.set()
            await self.fly_rtb()
            asyncio.create_task(self.shutdown(asyncio.get_running_loop()))

    async def monitor_atc(self):
        self.parser.handle_response_queue(True)
        await asyncio.sleep(10)
        self.parser.handle_response("request IFR clearance")
        self.parser.handle_response_queue()
        logger.info("Monitoring ATC")
        while not self.abort_event.is_set():
            meta_list = await asyncio.get_event_loop().run_in_executor(self.tp_executor, self.handle_stdin)
            for meta in meta_list:
                await self.command_queue.put(meta)

    def handle_stdin(self):
        command = sys.stdin.readline().rstrip()
        if command == "rtb":
            raise ControlError("Received RTB command input")
        return self.parser.handle_command(command)

    async def monitor_telem(self):
        logging.info("Monitoring State")
        async for telem in self.drone.telemetry.position():
            # logging.info(telem)
            if self.abort_event.is_set():
                break
            await asyncio.sleep(1)

    async def monitor_health(self):
        logging.info("Monitoring Health")
        trigger_state = True
        async for health_ok in self.drone.telemetry.health_all_ok():
            if self.abort_event.is_set():
                break
            if not health_ok and trigger_state:
                logging.warning("Drone health issue encountered")
                await self.print_telem_status()
                trigger_state = False
            if health_ok:
                trigger_state = True
            await asyncio.sleep(1)

    async def print_telem_status(self):
        async for is_armed in self.drone.telemetry.armed():
            logging.debug(f"Armed state:\n\t{is_armed}")
            break
        async for flight_mode in self.drone.telemetry.flight_mode():
            logging.debug(f"Flight mode:\n\t{flight_mode}")
            break
        async for landed_state in self.drone.telemetry.landed_state():
            logging.debug(f"Landed State:\n\t{landed_state}")
            break
        async for battery in self.drone.telemetry.battery():
            logging.debug(str(battery).replace(' [', '\n\t').replace(', ', '\n\t').replace(']', ''))
            break
        async for gps_info in self.drone.telemetry.gps_info():
            logging.debug(str(gps_info).replace(' [', '\n\t').replace(', ', '\n\t').replace(']', ''))
            break
        async for health in self.drone.telemetry.health():
            logging.debug(str(health).replace(' [', '\n\t').replace(', ', '\n\t').replace(']', ''))
            break
        async for position in self.drone.telemetry.position():
            logging.debug(str(position).replace(' [', '\n\t').replace(', ', '\n\t').replace(']', ''))
            break

    async def fly_commands(self):
        logging.info("Following ATC command queue")
        while not self.abort_event.is_set():
            mode, *args = await self.command_queue.get()
            logging.debug(f"Interpreting {mode, *args}")
            cmd_coro = self.mission_planner.fetch_command_coro(mode, *args)
            asyncio.create_task(cmd_coro)

    async def fly_rtb(self):
        logging.info("Attempt to land at nearest location")
        await self.drone.action.return_to_launch()
        logging.info("Returning Home")
        async for landed in self.drone.telemetry.landed_state():
            if landed == telemetry.LandedState.ON_GROUND:
                logging.info("Landed")
                break
        await asyncio.sleep(1)
        logging.info("Disarming drone")
        await self.drone.action.disarm()

    def handle_exception(self, loop, context):
        msg = context.get("exception", context["message"])
        logging.exception(f"Caught exception: {msg}")
        logging.debug(traceback.format_exc())
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
    vcs = Controller(System(), args.call_sign, args.serial)
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
    ARGS = parser.parse_args()
    config_logging.config_logging_stdout(logging.DEBUG if ARGS.verbose else logging.INFO)
    main(ARGS)
