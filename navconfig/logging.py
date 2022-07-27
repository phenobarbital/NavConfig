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
import os
from pathlib import Path
from navconfig import config, BASE_DIR, DEBUG
import logging
from logging.config import dictConfig

"""
Logging
"""
if DEBUG:
    loglevel = logging.DEBUG
else:
    loglevel = logging.INFO

APP_NAME = config.get('APP_NAME', fallback='navigator')
APP_TITLE = config.get('APP_TITLE', section='info', fallback='navigator')
LOG_DIR = config.get('logdir', section='logging', fallback=str(BASE_DIR.joinpath('logs')))
LOG_NAME = config.get('logname', section='logging', fallback=APP_TITLE)
TMP_DIR = config.get('temp_path', section='temp', fallback='/tmp')

"""
Logging Information.
"""
logstash_logging = config.getboolean(
    'logstash_enabled', section='logging', fallback=False)
logging_echo = config.getboolean(
    'logging_echo', section='logging', fallback=False)

logging_admin = config.get('logging_admin', section='logging', fallback="dev@domain.com")
logging_email = config.get('logging_email', section='logging', fallback='no-reply@domain.com')

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
    fallback=['StreamHandler', 'RotatingFileHandler', 'ErrorFileHandler']
)
if isinstance(HANDLERS, str):
    HANDLERS = HANDLERS.split(',')

logging_config = dict(
    version=1,
    disable_existing_loggers=False,
    formatters={
        "console": {
            'format': '%(message)s'
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
        'StreamHandler': {
                'class': 'logging.StreamHandler',
                'formatter': 'default',
                "stream": "ext://sys.stdout",
                'level': loglevel
        },
        'RotatingFileHandler': {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': '{0}/{1}.log'.format(LOG_DIR, LOG_NAME),
                'maxBytes': (1048576*5),
                'backupCount': 2,
                'encoding': 'utf-8',
                'formatter': 'file',
                'level': loglevel
        },
        'ErrorFileHandler': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': logging.ERROR,
                'filename': '{0}/{1}.error.log'.format(LOG_DIR, LOG_NAME),
                'formatter': 'error',
                'maxBytes': (1048576*5),
                'backupCount': 2,
                'mode': 'a',
         },
        'CriticalMailHandler': {
            'level': logging.CRITICAL,
            'formatter': 'error',
            'class': 'logging.handlers.SMTPHandler',
            'mailhost' : 'localhost',
            'fromaddr': logging_email,
            'toaddrs': [logging_admin],
            'subject': 'Critical Error on {}'.format(APP_NAME)
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
            "level": loglevel,
            "propagate": False
        },
    },
    root={
        'handlers': ['RotatingFileHandler', 'ErrorFileHandler', 'CriticalMailHandler'],
        'level': loglevel,
    },
)

if logging_echo is True:
    logging_config['handlers']['console'] = {
        "class": "logging.StreamHandler",
        "formatter": "default",
        "stream": "ext://sys.stdout",
        'level': logging.DEBUG
    }
    logging_config['root']['handlers'].append('console')

if logstash_logging:
    # basic configuration of Logstash
    import logstash_async
    LOGSTASH_HOST = config.get('LOGSTASH_HOST', fallback='localhost')
    LOGSTASH_PORT = config.get('LOGSTASH_PORT', fallback=6000)
    LOG_TAG = config.get('FLUENT_TAG', fallback='app.log')
    logging_config['formatters']['logstash'] = {
      '()': 'logstash_async.formatter.LogstashFormatter',
      'message_type': 'python-logstash',
      'fqdn': False,  # Fully qualified domain name. Default value: false.
      'extra_prefix': 'dev',
      'extra': {
          'application': '{}'.format(APP_NAME),
          'project_path': '{}'.format(BASE_DIR),
          'environment': 'production'
      }
    }
    logging_config['handlers']['LogstashHandler'] = {
            'class': 'logstash_async.handler.AsynchronousLogstashHandler',
            'formatter': 'logstash',
            'transport': 'logstash_async.transport.TcpTransport',
            'host': LOGSTASH_HOST,
            'port': LOGSTASH_PORT,
            'level': loglevel,
            'database_path': '{}/logstash.db'.format(LOG_DIR),
    }
    logging_config[APP_NAME]['handlers'] = [
        'LogstashHandler', 'StreamHandler'
    ]

"""
Load Logging Configuration:
"""
dictConfig(logging_config)
