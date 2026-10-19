import logging
from logging import config
import os
import yaml
from logging_tree import printout
from colorama import Fore, Back

from common_lib.config.client import ConfigClient


class ColorFormatter(logging.Formatter):
    # Change this dictionary to suit your coloring needs!
    COLORS = {
        "WARNING": Fore.YELLOW,
        #"ERROR": Fore.RED + Back.WHITE,
        "ERROR": Fore.RED,
        "DEBUG": Fore.BLUE,
        "INFO": Fore.GREEN,
        "CRITICAL": Fore.RED + Back.WHITE
    }

    def format(self, record):
        color = self.COLORS.get(record.levelname, "")
        if color:
            record.name = Fore.WHITE + record.name
            record.levelname = color + record.levelname + color
            #record.msg = Fore.WHITE + record.msg
        return logging.Formatter.format(self, record)

class EndpointFilter(logging.Filter):
    # Uvicorn endpoint access log filter
    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage().find("GET /metrics") == -1

def start_logging():

    app_name = ConfigClient.get_property(key="APP_NAME", section="DEFAULT")

    path_base = ConfigClient.get_base_path()
    config_logging = path_base / 'config' / 'logging.yaml'

    with open(config_logging, 'r', encoding='utf-8') as file:
        yml = yaml.safe_load(file)

    handlers = ConfigClient.get_property(key="HANDLERS", section="LOG").split(',')
    
    if 'file' not in handlers :
        del yml['handlers']['file']
    else :
        yml['handlers']['file']['filename'] = yml['handlers']['file']['filename'].replace('__app_name__', app_name)


    for logger in yml['loggers'] :
        yml['loggers'][logger]['handlers'] = handlers

    logging.config.dictConfig( yml )
    logger = logging.getLogger('service')

    logger.info("Detected environment : %s", os.getenv("APP_ENV"))

    # pylint: disable=E1101
    for l in [ logging.getLogger(name) for name in logging.root.manager.loggerDict ] :
        if l.level != 0 :
            logger.debug('Logger %s set to level %s', l.name, str(logging.getLevelName(l.level)))
    # pylint: enable=E1101

    # Filter out /endpoint (filtering /metrics)
    logging.getLogger("uvicorn.access").addFilter(EndpointFilter())

    # Print logging tree
    #printout()

