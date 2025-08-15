"""
Log Configuration.

Logging configuration.

Supports:
    - Mail Critical Handler
    - Rotating File handler
    - Console (debug) Handler with Colors
    - Error File Handler
    TODO: add a Telegram Critical Handler.

"""
from pathlib import Path
from logging.config import dictConfig
from navconfig import config, BASE_DIR
from .logger import logging, Logger, LOGLEVEL, ColoredFormatter

### Logging
loglevel = LOGLEVEL

APP_NAME = config.get("APP_NAME", fallback="navigator")
LOG_DIR = config.get(
    "logdir", section="logging", fallback=str(BASE_DIR.joinpath("logs"))
)
TMP_DIR = config.get("temp_path", section="temp", fallback="/tmp")

"""
Logging Information.
"""
logging_disable_other = config.getboolean(
    "logging_disable_other", section="logging", fallback=False
)

### Logging Echo (standard output) - FIXED: Default to True for colored output
logging_echo = config.getboolean(
    "logging_echo",
    section="logging",
    fallback=True  # Changed from False to True
)

## Mail Alerts:
logging_enable_mailer = config.getboolean(
    "mailer_enabled", section="logging", fallback=False
)

## can disable the rotating file handler
logging_enable_filehandler = config.getboolean(
    "filehandler_enabled", section="logging", fallback=False
)

### External Loggers:
logging_enable_logstash = config.getboolean(
    "logstash_enabled", section="logging", fallback=False
)

# Path version of the log directory
logdir = Path(LOG_DIR).resolve()
if not logdir.exists():
    try:
        logdir.mkdir(parents=True, exist_ok=True)
    except OSError:
        logging.exception("Error Creating Logging Directory", exc_info=True)

HANDLERS = config.get("handlers", section="logging", fallback=["console"])
if isinstance(HANDLERS, str):
    HANDLERS = HANDLERS.split(",")

# FIXED: Improved logging configuration to avoid duplicates
logging_config = dict(
    version=1,
    disable_existing_loggers=logging_disable_other,
    formatters={
        "console": {
            "()": ColoredFormatter,
            "datefmt": "%Y-%m-%d %H:%M:%S"
        },
        "default": {
            "format": "[%(levelname)s] %(asctime)s %(name)s|%(lineno)d :: %(message)s",  # noqa
            "datefmt": "%Y-%m-%d %H:%M:%S"
        },
        "error": {
            "format": "%(asctime)s-%(levelname)s-%(name)s-%(process)d::"
                      "%(module)s|%(lineno)s:: %(message)s"
        },
        "file": {
            "format": "%(asctime)s: [%(levelname)s]: %(pathname)s: %(lineno)d:"
                      "\n%(message)s\n"
        },
    },
    handlers={
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "console",
            "stream": "ext://sys.stdout",
            "level": loglevel,
        },
        "StreamHandler": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "stream": "ext://sys.stdout",
            "level": loglevel,
        },
        "null": {
            "class": "logging.NullHandler",
        },
    },
    loggers={
        APP_NAME: {
            "handlers": ["console"] if logging_echo else ["null"],
            "level": loglevel,
            "propagate": False
        },
        "__main__": {  # if __name__ == "__main__"
            "handlers": ["console"] if logging_echo else ["null"],
            "level": "INFO",
            "propagate": False,
        },
        "": {  # root logger
            "handlers": ["console"] if logging_echo else ["null"],
            "level": "INFO",
            "propagate": False
        },
    },
    root={
        "handlers": ["console"] if logging_echo else ["null"],
        "level": loglevel,
        "propagate": False,  # IMPORTANT: Set to False to avoid duplicates
    },
)

# FIXED: Don't add console handler to root if already using console
# This was causing the duplicate messages
# Remove the problematic line:
# if logging_echo is True:
#     logging_config["root"]["handlers"].append("console")

# Instead, handle file logging separately
if logging_enable_filehandler is True:
    from .handlers.file import FileHandler

    lf = FileHandler(config=config, loglevel=loglevel, application=APP_NAME)
    logging_config["handlers"]["RotatingFileHandler"] = lf.handler(
        path=LOG_DIR
    )
    ## Also Error Handler:
    logging_config["handlers"]["ErrorFileHandler"] = lf.handler(
        path=LOG_DIR, loglevel=logging.ERROR
    )

    # Add file handlers to all relevant loggers
    for logger_name in [APP_NAME, "__main__", ""]:
        if logger_name in logging_config["loggers"]:
            logging_config["loggers"][logger_name]["handlers"].extend([
                "RotatingFileHandler", "ErrorFileHandler"
            ])

    # Add to root as well
    logging_config["root"]["handlers"].extend([
        "RotatingFileHandler", "ErrorFileHandler"
    ])

if logging_enable_mailer is True:
    from .handlers.mail import MailerHandler

    lm = MailerHandler(
        config=config,
        loglevel=logging.CRITICAL,
        application=APP_NAME
    )
    logging_config["handlers"]["CriticalMailHandler"] = lm.handler()

    # Add mail handler to all relevant loggers
    for logger_name in [APP_NAME, "__main__", ""]:
        if logger_name in logging_config["loggers"]:
            logging_config["loggers"][logger_name]["handlers"].append(
                "CriticalMailHandler"
            )

    logging_config["root"]["handlers"].append("CriticalMailHandler")

if logging_enable_logstash is True:
    logging.debug("Logstash configuration Enabled.")
    ### Importing Logstash Handler and returning Logging Config:
    from .handlers.logstash import LogstashHandler

    logstash_logging = config.get(
        "logstash_logging", section="logging", fallback="INFO"
    )

    lh = LogstashHandler(
        config=config,
        loglevel=logstash_logging,
        application=APP_NAME
    )

    if lh.logstash_available():
        logging_config["formatters"]["logstash"] = lh.formatter(path=BASE_DIR)
        logging_config["handlers"]["LogstashHandler"] = lh.handler(
            enable_localdb=config.getboolean(
                "LOGSTASH_ENABLE_DB",
                fallback=True
            ),
            logdir=LOG_DIR,
        )

        # Add logstash handler to all relevant loggers
        for logger_name in [APP_NAME, "__main__", ""]:
            if logger_name in logging_config["loggers"]:
                logging_config["loggers"][logger_name]["handlers"].append(
                    "LogstashHandler"
                )

        logging_config["root"]["handlers"].append("LogstashHandler")
    else:
        logging.error(
            (
                "Logstash Logging is enabled but Logstash server "
                "is Unavailable, please start Logstash Server."
            )
        )

### Load Logging Configuration:
dictConfig(logging_config)

### configure basic logger for navconfig
logger = Logger(name=__name__, config=logging_config)


# alias for debug printing
class dprint:
    instance: object = None

    def __new__(cls, *args, **kwargs):
        if not cls.instance:
            cls.instance = Logger(name="DEBUG", config=logging_config)
            cls.instance.addConsole()
        cls.instance.debug(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        self.instance.debug(*args, **kwargs)
