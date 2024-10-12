import os
import sys
import logging
from navconfig import BASE_DIR, DEBUG


os.chdir(str(BASE_DIR))

# Reduce asyncio log level:
logging.getLogger('asyncio').setLevel(logging.INFO)


# Debug
LOCAL_DEVELOPMENT = DEBUG is True and sys.argv[0] == "run.py"

### Global-Settings.
try:
    from settings.settings import *  # pylint: disable=W0401,W0614 # noqa
except ImportError as err:
    try:
        from settings import *  # pylint: disable=W0401,W0614 # noqa
    except ImportError as err:
        logging.error("There is no *settings/* module in project.")
        print(
            "Settings.py File is missing."
            "Hint: Its recommended to use a settings/settings.py"
            " or settings/__init__.py module to customize your "
            " Configuration."
        )
### User Local Settings
try:
    from settings.local_settings import *  # pylint: disable=W0401,W0614 # noqa
except ImportError as err:
    pass
