import os
import logging
from navconfig import (
    BASE_DIR
)
os.chdir(str(BASE_DIR))

### Global-Settings.
try:
    from settings.settings import * # pylint: disable=W0401,W0614
except ImportError as err:
    try:
        from settings import settings
        logging.error(f'Cannot loaded a settings Module {err}, module: {settings}')
        print(
            'Settings.py File is missing.'
            'Hint: Its recommended to use a settings/settings.py module to customize '
            ' NAV Configuration.'
        )
    except ImportError as ex:
        logging.error("There is no *settings/* module in project.")
        print(
            'Settings.py module is missing.'
            'Hint: Its recommended to use a settings/settings.py module to customize '
            ' NAV Configuration.'
        )
### User Local Settings
try:
    from settings.local_settings import * # pylint: disable=W0401,W0614
except (ImportError) as err:
    pass
