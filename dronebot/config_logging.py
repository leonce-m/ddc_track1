import logging
import sys
import os
import time
import pkgutil

def config_logging_stdout(level, full=False):
    if full:
        formatter = logging.Formatter("{asctime} {levelname}:{name}:{message}", style='{')
    else:
        formatter = logging.Formatter('%(levelname)s: %(message)s')

    cons_handler = logging.StreamHandler(sys.stdout)
    cons_handler.setLevel(logging.DEBUG)
    cons_handler.setFormatter(formatter)

    log_file = 'logs/dronebot_' + time.strftime("%Y-%m-%d-%T") + '.log'
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    file_handler = logging.FileHandler(log_file, mode='a')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.addHandler(cons_handler)
    root_logger.addHandler(file_handler)

    for _, module_name, _ in pkgutil.iter_modules([__package__]):
        logger = logging.getLogger(f"dronebot.{module_name}".upper())
        logger.setLevel(level)
    logging.getLogger('__MAIN__').setLevel(level)
