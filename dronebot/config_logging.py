import logging
import sys

def config_logging_stdout(level, name=None, full=False):
    if full:
        formatter = logging.Formatter("{asctime} {levelname}:{name}:{message}", style='{')
    else:
        formatter = logging.Formatter('%(levelname)s:%(name)s: %(message)s')

    cons_handler = logging.StreamHandler(sys.stdout)
    cons_handler.setLevel(logging.DEBUG)
    cons_handler.setFormatter(formatter)

    file_handler = logging.FileHandler('logs/dronebot_%(asctime)s.log')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.addHandler(cons_handler)
    root_logger.addHandler(file_handler)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    return logger
