import os
import sys
import logging
from pathlib import Path

from .config import navigatorConfig
config = navigatorConfig()

DEBUG = os.getenv('DEBUG', False)
BASE_DIR = Path(os.getenv('BASE_DIR', config.site_root)).resolve()
SETTINGS_DIR = BASE_DIR.joinpath('settings')

if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

if str(SETTINGS_DIR) not in sys.path:
    sys.path.append(str(SETTINGS_DIR))


try:
    from settings.settings import *
except (ImportError, ModuleNotFoundError):
    # running inside django project:
    print('Its recommended to use a settings/settings module to customize Navigator Configuration')

"""
User Local Settings
"""
try:
    from settings.local_settings import *
except (ImportError, ModuleNotFoundError):
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
