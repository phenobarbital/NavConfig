"""
NavConfig.

Main object for Configuration of several Navigator-related Tools.
"""
import sys
import os
from pathlib import Path
from .version import (
    __title__, __description__, __version__, __author__, __author_email__
)
from .utils import project_root
from .config import navigatorConfig # noqa


# PROJECT PATH IS DEFINED?
SITE_ROOT = project_root(__file__)
BASE_DIR = os.getenv('BASE_DIR', None)
if not BASE_DIR:
    BASE_DIR = SITE_ROOT
else:
    BASE_DIR = Path(BASE_DIR).resolve()

SETTINGS_DIR = BASE_DIR.joinpath('settings')
# configuration of the environment type:
# environment type can be a file (.env) an encrypted file (crypt)
ENV_TYPE = os.getenv('ENV_TYPE', 'file')

"""
Loading main Configuration Object.
"""
config = navigatorConfig(SITE_ROOT, env_type = ENV_TYPE)
# ENV version (dev, prod, staging)
ENV = config.ENV

# DEBUG VERSION
DEBUG = config.debug

# SECURITY WARNING: keep the secret keys used in production secret!
PRODUCTION = config.getboolean('PRODUCTION', fallback=bool(not DEBUG))

# Add Path Navigator to Sys path
sys.path.append(str(BASE_DIR))
sys.path.append(str(SETTINGS_DIR))
