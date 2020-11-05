import sys
import os
from pathlib import Path
from .config import navigatorConfig

def is_virtualenv():
    return (hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix))

# PROJECT PATH IS DEFINED?
SITE_ROOT = os.getenv('SITE_ROOT', None)

if not SITE_ROOT:
    # get Project PATH
    if is_virtualenv():
        SITE_ROOT = Path(sys.prefix).resolve().parent
    else:
        SITE_ROOT = Path(os.path.abspath(os.path.dirname(__file__))).resolve().parent.parent
    if not SITE_ROOT:
        SITE_ROOT = Path(sys.prefix).resolve().parent
else:
    SITE_ROOT = Path(SITE_ROOT).resolve()

# adding BASE_DIR for compatibility with Django
BASE_DIR = os.getenv('BASE_DIR', None)
if not BASE_DIR:
    BASE_DIR = SITE_ROOT
else:
    BASE_DIR = Path(BASE_DIR).resolve()

# for running DataIntegrator
SERVICES_DIR = BASE_DIR.joinpath('services')
SETTINGS_DIR = BASE_DIR.joinpath('settings')
EXTENSION_DIR = BASE_DIR.joinpath('extensions')

config = navigatorConfig(SITE_ROOT)

ENV = config.ENV
DEBUG = os.getenv('DEBUG', False)
# SECURITY WARNING: keep the secret key used in production secret!
PRODUCTION = config.getboolean('PRODUCTION', fallback=bool(not DEBUG))
LOCAL_DEVELOPMENT = (DEBUG == True and sys.argv[0] == 'run.py')

# Add Path Navigator to Sys path
sys.path.append(str(BASE_DIR))
sys.path.append(str(SERVICES_DIR))
sys.path.append(str(SETTINGS_DIR))
sys.path.append(str(EXTENSION_DIR))

from .conf import *
