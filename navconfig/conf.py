import os
import sys
import logging
from pathlib import Path
from navconfig import (
    BASE_DIR
)
os.chdir(str(BASE_DIR))

"""
Global-Settings.
"""
try:
    from settings.settings import *
except (ImportError, ModuleNotFoundError) as err:
    from settings import settings
    logging.error(f'Cannot loaded a settings Module {err}, module: {settings}')
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
except (ImportError, ModuleNotFoundError) as err:
    pass
