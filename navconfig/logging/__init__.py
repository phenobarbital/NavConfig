"""
Log Configuration.

Logging configuration.

Supports:
 - Mail Critical Handler
 - Rotating File handler
 - Console (debug) Handler
 - Error File Handler
 TODO: add a Telegram Critical Handler.

"""
from pathlib import Path
from logging.config import dictConfig
from navconfig import config, BASE_DIR
from .logger import logging, Logger, LOGLEVEL, ColoredFormatter

### Logging
loglevel = LOGLEVEL

APP_NAME = config.get('APP_NAME', fallback='navigator')
APP_TITLE = config.get('APP_TITLE', section='info', fallback='navigator')
LOG_DIR = config.get(
    'logdir', section='logging', fallback=str(BASE_DIR.joinpath('logs'))
)
LOG_NAME = config.get('logname', section='logging', fallback=APP_TITLE)
TMP_DIR = config.get('temp_path', section='temp', fallback='/tmp')

"""
Logging Information.
"""
logstash_logging = config.getboolean(
    'logstash_enabled', section='logging', fallback=False)

logging_disable_other = config.getboolean(
    'logging_disable_other', section='logging', fallback=False
)

## disable mail alerts:
logging_enable_mailer = config.getboolean(
    'logging_enable_mailer', section='logging', fallback=False
)
logging_echo = config.getboolean(
    'logging_echo', section='logging', fallback=False)
## can disable the rotating file handler
logging_enable_filehandler = config.getboolean(
    'logging_enable_filehandler', section='logging', fallback=False
)

logging_host = config.get(
    'logging_host', section='logging', fallback="localhost"
)
logging_admin = config.get(
    'logging_admin', section='logging', fallback="dev@domain.com"
)
logging_email = config.get(
    'logging_email', section='logging', fallback='no-reply@domain.com'
)

# Path version of the log directory
logdir = Path(LOG_DIR).resolve()
if not logdir.exists():
    try:
        logdir.mkdir(parents=True, exist_ok=True)
    except OSError:
        logging.exception('Error Creating Logging Directory', exc_info=True)

HANDLERS = config.get(
    'handlers',
    section='logging',
    fallback=['StreamHandler', 'ErrorFileHandler']
)
if isinstance(HANDLERS, str):
    HANDLERS = HANDLERS.split(',')

logging_config = dict(
    version=1,
    disable_existing_loggers=logging_disable_other,
    formatters={
        "console": {
            '()': ColoredFormatter,
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        'default': {
            'format': '[%(levelname)s] %(asctime)s %(name)s|%(lineno)d :: %(message)s'
        },
        'error': {
            'format': '%(asctime)s-%(levelname)s-%(name)s-%(process)d::%(module)s|%(lineno)s:: %(message)s'
        },
        'file': {
            'format': "%(asctime)s: [%(levelname)s]: %(pathname)s: %(lineno)d: \n%(message)s\n"
        },
    },
    handlers={
        'console': {
            "class": "logging.StreamHandler",
            "formatter": "console",
            "stream": "ext://sys.stdout",
            'level': loglevel
        },
        'StreamHandler': {
            'class': 'logging.StreamHandler',
            'formatter': 'default',
            "stream": "ext://sys.stdout",
            'level': loglevel
        },
        'ErrorFileHandler': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': logging.ERROR,
            'filename': f'{LOG_DIR}/{LOG_NAME}.error.log',
            'formatter': 'error',
            'maxBytes': (1048576 * 5),
            'backupCount': 2,
            'mode': 'a',
        }
    },
    loggers={
        APP_NAME: {
            'handlers': HANDLERS,
            'level': loglevel,
            'propagate': False
        },
        "__main__": {  # if __name__ == "__main__"
            "handlers": ["StreamHandler"],
            "level": 'INFO',
            "propagate": False
        },
        '': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False
        }
    },
    root={
        'handlers': ['ErrorFileHandler'],
        'level': loglevel,
    },
)

if logging_enable_filehandler is True:
    logging_config['handlers']['RotatingFileHandler'] = {
        'class': 'logging.handlers.RotatingFileHandler',
        'filename': f'{LOG_DIR}/{LOG_NAME}.log',
        'maxBytes': (1048576 * 5),
        'backupCount': 2,
        'encoding': 'utf-8',
        'formatter': 'file',
        'level': loglevel
    }
    logging_config['root']['handlers'].append('RotatingFileHandler')

if logging_enable_mailer is True:
    logging_config['handlers']['CriticalMailHandler'] = {
        'level': logging.CRITICAL,
        'formatter': 'error',
        'class': 'logging.handlers.SMTPHandler',
        'mailhost': logging_host,
        'fromaddr': logging_email,
        'toaddrs': [logging_admin],
        'subject': f'Critical Error on {APP_NAME}'
    }
    logging_config['root']['handlers'].append('CriticalMailHandler')

if logging_echo is True:
    logging_config['root']['handlers'].append('console')

if logstash_logging:
    logging.debug(
        "Logstash configuration Enabled."
    )
    environment = config.ENV if config.ENV is not None else 'production'
    # basic configuration of Logstash
    try:
        import logstash_async  # pylint: disable=W0611
    except ImportError as ex:
        raise RuntimeError(
            "NavConfig: Logstash Logging is enabled but Logstash async \
                dependency is not installed.\
            Hint: run 'pip install logstash_async'."
        ) from ex
    LOGSTASH_HOST = config.get('LOGSTASH_HOST', fallback='localhost')
    LOGSTASH_PORT = config.getint('LOGSTASH_PORT', fallback=6000)
    LOG_TAG = config.get('FLUENT_TAG', fallback='app.log')
    logging_config['formatters']['logstash'] = {
        '()': 'logstash_async.formatter.LogstashFormatter',
        'message_type': 'python-logstash',
        'fqdn': False,  # Fully qualified domain name. Default value: false.
        'extra_prefix': 'dev',
        'extra': {
            'application': f'{APP_NAME}',
            'project_path': f'{BASE_DIR}',
            'environment': environment
        }
    }
    logging_config['handlers']['LogstashHandler'] = {
        'class': 'logstash_async.handler.AsynchronousLogstashHandler',
        'formatter': 'logstash',
        'transport': 'logstash_async.transport.TcpTransport',
        'host': LOGSTASH_HOST,
        'port': int(LOGSTASH_PORT),
        'level': loglevel,
        'database_path': f'{LOG_DIR}/logstash.db',
    }
    if 'root' not in logging_config:
        logging_config['root'] = {}
    if 'handlers' not in logging_config['root']:
        logging_config['root']['handlers'] = []
    logging_config['root']['handlers'].extend(
        ['LogstashHandler', 'StreamHandler']
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
            cls.instance = Logger(name='DEBUG', config=logging_config)
            cls.instance.addConsole()
        cls.instance.debug(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        self.instance.debug(*args, **kwargs)
