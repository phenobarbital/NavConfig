import os
import sys
import logging
from pathlib import Path

from navconfig import config, BASE_DIR, DEBUG, PRODUCTION, SETTINGS_DIR
print('DEBUG: ', DEBUG)
print('SETTINGS PATH: ', SETTINGS_DIR)

if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

if str(SETTINGS_DIR) not in sys.path:
    sys.path.append(str(SETTINGS_DIR))

# CACHE INFO
CACHE_HOST = config.get('CACHEHOST', fallback='localhost')
CACHE_PORT = config.get('CACHEPORT', fallback=6379)
CACHE_URL = "redis://{}:{}".format(CACHE_HOST, CACHE_PORT)

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
