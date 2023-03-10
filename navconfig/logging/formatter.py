import logging

class ColoredFormatter(logging.Formatter):

    grey = "\x1b[38;20m"
    green = '\x1b[32m'
    purple = "\033[35m"
    cyan = "\033[36m"
    yellow = "\x1b[33;20m"
    orange = "\033[33m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    lightgrey = "\033[37m"
    reset = "\x1b[0m"
    _format = "[%(levelname)s] %(asctime)s %(name)s(%(filename)s:%(lineno)d) :: %(message)s"

    FORMATS = {
        logging.DEBUG: green + _format + reset,
        logging.INFO: grey + _format + reset,
        logging.WARNING: yellow + _format + reset,
        logging.ERROR: orange + _format + reset,
        logging.CRITICAL: bold_red + _format + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)
