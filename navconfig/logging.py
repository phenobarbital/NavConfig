"""
Log Configuration.

Logging configuration
"""
import os
import logging
import logstash_async

from .config import navigatorConfig
config = navigatorConfig()

DEBUG = os.getenv('DEBUG', False)

"""
Logging
"""
if DEBUG:
    loglevel = logging.DEBUG
else:
    loglevel = logging.INFO


logdir = config.get('logdir', section='logging', fallback='/tmp')
LOG_DIR = config.get('logdir', section='logging', fallback='/var/log/troc')
LOG_NAME = config.get('logname', section='logging', fallback='navigator')

# basic configuration of Logstash
LOGSTASH_HOST = config.get('LOGSTASH_HOST', fallback='localhost')
LOGSTASH_PORT = config.get('LOGSTASH_PORT', fallback=5044)

HANDLERS = config.get(
    'handlers',
    section='logging',
    fallback=['console', 'StreamHandler']
)
if isinstance(HANDLERS, str):
    HANDLERS = HANDLERS.split(',')

logging_config = dict(
    version=1,
    disable_existing_loggers=True,
    formatters={
        "console": {
            'format': '%(message)s'
        },
        'default': {
            'format': '[%(levelname)s] %(asctime)s %(name)s: %(message)s'
        },
        'error': {
            'format': '%(asctime)s-%(levelname)s-%(name)s-%(process)d::%(module)s|%(lineno)s:: %(message)s'
        },
        'file': {
            'format': "%(asctime)s: [%(levelname)s]: %(pathname)s: %(lineno)d: \n%(message)s\n"
        },
        'logstash': {
          '()': 'logstash_async.formatter.LogstashFormatter',
          'message_type': 'python-logstash',
          'fqdn': False,  # Fully qualified domain name. Default value: false.
          'extra_prefix': 'dev',
          'extra': {
              'application': 'Navigator',
              'project_path': 'Navigator',
              'environment': 'production'
          }
        }
    },
    handlers={
        "console": {
                "formatter": "console",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                'level': logging.DEBUG
        },
        'StreamHandler': {
                'class': 'logging.StreamHandler',
                'formatter': 'default',
                'stream': 'ext://sys.stdout',
                'level': loglevel
        },
        'RotatingFileHandler': {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': '{0}/{1}.log'.format(LOG_DIR, LOG_NAME),
                'mode': 'a',
                'maxBytes': (1048576*5),
                'backupCount': 2,
                'encoding': 'utf-8',
                'formatter': 'file'
        },
        'ErrorFileHandler': {
                'level': logging.ERROR,
                'filename': '{0}/{1}.error.log'.format(LOG_DIR, LOG_NAME),
                'formatter': 'error',
                'class': 'logging.FileHandler',
                'mode': 'a',
        },
        'LogstashHandler': {
                'class': 'logstash_async.handler.AsynchronousLogstashHandler',
                'host': LOGSTASH_HOST,
                'port': LOGSTASH_PORT,
                'transport': 'logstash_async.transport.TcpTransport',
                'formatter': 'logstash',
                'level': loglevel,
                'database_path': '{}/logstash.db'.format(LOG_DIR),
        }
        },
    root={
        'handlers': HANDLERS,
        'level': loglevel,
    },
)
