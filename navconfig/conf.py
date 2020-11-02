import os
import sys
import logging

from .config import navigatorConfig
config = navigatorConfig()

DEBUG = os.getenv('DEBUG', False)
BASE_DIR = os.getenv('BASE_DIR', config.site_root)
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

try:
    from settings.settings import *
except ImportError:
    # running inside django project:
    try:
        from navigator.settings.settings import *
    except ImportError:
        print('Its recommended to use a settings/settings module to customize Navigator Configuration')

"""
User Local Settings
"""
try:
    from settings.local_settings import *
except ImportError:
    try:
        from navigator.settings.local_settings import *
    except ImportError:
        pass

"""
Logging
"""
logdir = config.get('logdir', section='logging', fallback='/tmp')
if DEBUG:
    loglevel = logging.DEBUG
else:
    loglevel = logging.INFO
logging_config = dict(
    version = 1,
    formatters = {
        "console": {
            'format': '%(message)s'
        },
        "file": {
            "format": "%(asctime)s: [%(levelname)s]: %(pathname)s: %(lineno)d: \n%(message)s\n"
        },
        'default': {
            'format': '[%(levelname)s] %(asctime)s %(name)s: %(message)s'}
        },
    handlers = {
        "console": {
                "formatter": "console",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                'level': loglevel
        },
        'StreamHandler': {
                'class': 'logging.StreamHandler',
                'formatter': 'default',
                'level': loglevel
        },
        'RotatingFileHandler': {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': '{0}/{1}.log'.format(logdir, 'query_api'),
                'maxBytes': (1048576*5),
                'backupCount': 2,
                'encoding': 'utf-8',
                'formatter': 'file',
                'level': loglevel}
        },
    root = {
        'handlers': ['StreamHandler','RotatingFileHandler'],
        'level': loglevel,
        },
)
