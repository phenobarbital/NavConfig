import os
import contextlib
import sys
import logging
from navconfig import BASE_DIR, DEBUG

os.chdir(str(BASE_DIR))

# Reduce asyncio log level:
logging.getLogger('asyncio').setLevel(logging.INFO)

# Debug
LOCAL_DEVELOPMENT = DEBUG is True and sys.argv[0] == "run.py"

### Load Global-Settings if available (optional).
### The settings package is not mandatory for navconfig to work.
with contextlib.suppress(ImportError):
  ### Global-Settings.
  try:
      from settings.settings import *  # pylint: disable=W0401,W0614 # noqa
  except ImportError as err:
      try:
          from settings.settings import *  # pylint: disable=W0401,W0614 # noqa
      except ImportError:
          try:
              from settings import *  # pylint: disable=W0401,W0614 # noqa
          except ImportError:
              pass