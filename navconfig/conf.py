import os
import sys
import logging
from pathlib import Path

from .config import navigatorConfig
config = navigatorConfig()

DEBUG = os.getenv('DEBUG', False)
BASE_DIR = Path(os.getenv('BASE_DIR', config.site_root)).resolve()
SETTINGS_DIR = BASE_DIR.joinpath('settings')
print('SETTINGS PATH: ', SETTINGS_DIR)

if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

if str(SETTINGS_DIR) not in sys.path:
    sys.path.append(str(SETTINGS_DIR))

try:
    from settings.settings import *
except (ImportError, ModuleNotFoundError) as err:
    print(err)
    # running inside django project:
    print('Its recommended to use a settings/settings module to customize Navigator Configuration')

"""
User Local Settings
"""
try:
    from settings.local_settings import *
except (ImportError, ModuleNotFoundError):
    pass
