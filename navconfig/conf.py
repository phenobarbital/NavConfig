import os
import sys
import logging
from pathlib import Path
from navconfig import (
    SETTINGS_DIR
)

"""
Global-Settings.
"""
try:
    sys.path.append(str(SETTINGS_DIR))
    from settings.settings import *
except (ImportError, ModuleNotFoundError) as err:
    print(err)
    logging.error(f'Cannot load settings Module {err}')
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
