import logging
from logging import getLoggerClass, addLevelName, NOTSET


VERBOSE_LEVEL_NUM = 11
logging.VERBOSE = VERBOSE_LEVEL_NUM

NOTICE_LEVEL_NUM = 12
logging.NOTICE = NOTICE_LEVEL_NUM

# Set the VERBOSE level name globally
addLevelName(VERBOSE_LEVEL_NUM, "VERBOSE")
# Set the NOICE level name globaly:
addLevelName(NOTICE_LEVEL_NUM, "NOTICE")


class VerboseLogger(getLoggerClass()):
    def __init__(self, name, level=NOTSET):
        super().__init__(name, level)

    def verbose(self, msg, *args, **kwargs):
        if self.isEnabledFor(VERBOSE_LEVEL_NUM):
            self._log(VERBOSE_LEVEL_NUM, msg, args, **kwargs)

    def notice(self, msg, *args, **kwargs):
        if self.isEnabledFor(NOTICE_LEVEL_NUM):
            self._log(NOTICE_LEVEL_NUM, msg, args, **kwargs)


class ColoredFormatter(logging.Formatter):
    lightgrey = "\033[37m"
    darkgrey = "\033[90m"
    green = "\x1b[32m"
    lightgreen = "\x1b[92m"
    blue = "\033[34m"
    lightblue = "\033[94m"
    purple = "\033[35m"
    cyan = "\033[36m"
    yellow = "\x1b[33;20m"
    lightyellow = "\033[93;1m"
    orange = "\033[33m"
    red = "\x1b[31;20m"
    lightred = "\033[91m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    _format = (
        "[%(levelname)s] %(asctime)s %(name)s(%(filename)s:%(lineno)d) :: %(message)s"
    )
    _notice = "[%(levelname)s] %(asctime)s :: %(message)s"

    FORMATS = {
        logging.DEBUG: green + _format + reset,
        logging.VERBOSE: lightgreen + _format + reset,
        logging.NOTICE: lightblue + _notice + reset,
        logging.INFO: lightgrey + _format + reset,
        logging.WARNING: yellow + _format + reset,
        logging.ERROR: lightyellow + _format + reset,
        logging.CRITICAL: bold_red + _format + reset,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)
