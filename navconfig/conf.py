import os
import contextlib
import logging
from navconfig import BASE_DIR

os.chdir(str(BASE_DIR))

# Reduce asyncio log level:
logging.getLogger('asyncio').setLevel(logging.INFO)

### Load Global-Settings if available (optional).
### The settings package is not mandatory for navconfig to work.
with contextlib.suppress(ImportError):
    try:
        from settings.settings import *  # pylint: disable=W0401,W0614 # noqa
    except ImportError:
        from settings import *  # pylint: disable=W0401,W0614 # noqa
