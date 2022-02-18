import os
import sys
from pathlib import Path
from navconfig import (
    config,
    BASE_DIR,
    DEBUG,
    PRODUCTION,
    SETTINGS_DIR
)

if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

if str(SETTINGS_DIR) not in sys.path:
    sys.path.append(str(SETTINGS_DIR))

"""
Global-Settings.
"""
try:
    from settings.settings import *
except (ImportError, ModuleNotFoundError) as err:
    print(err)
    # running inside django project:
    print(
        'Settings.py module is missing.'
        'Hint: Its recommended to use a settings/settings.py module to customize '
        ' Navigator Configuration.'
    )

"""
User Local Settings
"""
try:
    from settings.local_settings import *
except (ImportError, ModuleNotFoundError):
    pass
