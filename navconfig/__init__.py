"""
NavConfig.

Configuration management for Python projects.
"""
import sys
import logging
from .project import (
    project_root,
    get_env_type,
    get_environment
)
from .utils import install_uvloop
from .kardex import Kardex  # noqa
from .version import __version__

install_uvloop()

# Reduce asyncio log level:
logging.getLogger('asyncio').setLevel(logging.INFO)

# PROJECT PATH IS DEFINED?
SITE_ROOT, BASE_DIR = project_root(__file__)

## Settings Directory
SETTINGS_DIR = BASE_DIR.joinpath("settings")

# configuration of the environment type:
ENV_TYPE = get_env_type()

# ENV version (dev, prod, staging)
ENV = get_environment()

"""
Loading main Configuration Object.
"""
config = Kardex(SITE_ROOT, env=ENV, env_type=ENV_TYPE)

# DEBUG VERSION
DEBUG = config.debug
PRODUCTION = config.getboolean('PRODUCTION', fallback=bool(not DEBUG))
# Environment
ENVIRONMENT = config.get('ENVIRONMENT', fallback='development')
ENV = config.get('ENV', fallback='dev')

# Add Path Navigator to Sys path
sys.path.append(str(BASE_DIR))

# Add Path settings to Sys path if exists.
if SETTINGS_DIR.exists():
    sys.path.append(str(SETTINGS_DIR))
