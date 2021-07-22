import argparse
import logging
from dronebot import config_logging
from dronebot.controller import main

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Control PIXHAWK via MavSDK-Python with ATC commands (and respond)")
    parser.add_argument('-c', '--call_sign', default="cityairbus1234",
                        help="Set custom call sign")
    parser.add_argument('-s', '--serial', default="udp://:14550",
                        help="Set system address for drone serial port connection")
    parser.add_argument('-v', '--verbose', action='store_true',
                        help="Set logging level to DEBUG")
    ARGS = parser.parse_args()
    logger = config_logging.config_logging_stdout(logging.DEBUG if ARGS.verbose else logging.INFO)
    main(ARGS)