"""
NavConfig.

Configuration management for Python projects.
"""
import sys
from .project import (
    project_root,
    get_env_type,
    get_environment
)
from .kardex import Kardex  # noqa
from .version import __version__

# PROJECT PATH IS DEFINED?
SITE_ROOT, BASE_DIR = project_root(__file__)

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

## Settings Directory
SETTINGS_DIR = BASE_DIR.joinpath("settings")

# Add Path Navigator to Sys path
sys.path.append(str(BASE_DIR))
sys.path.append(str(SETTINGS_DIR))
