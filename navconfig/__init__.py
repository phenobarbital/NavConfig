"""
NavConfig.

Configuration management for Python projects.
"""
import sys
import logging
from typing import Any
from .project import (
    project_root,
    get_env_type,
    get_environment
)
from .utils import install_uvloop
from .utils.settings import ensure_settings_priority
from .kardex import Kardex  # noqa
from .version import __version__

install_uvloop()

# Reduce asyncio log level:
logging.getLogger('asyncio').setLevel(logging.INFO)


#: Names that are resolved on first access instead of at import time.
_LAZY_NAMES: tuple = (
    "SITE_ROOT",
    "BASE_DIR",
    "SETTINGS_DIR",
    "ENV_TYPE",
    "ENV",
    "config",
    "DEBUG",
    "PRODUCTION",
    "ENVIRONMENT",
)

__all__ = ("Kardex", "bootstrap", "__version__", *_LAZY_NAMES)

_bootstrapped: bool = False


def bootstrap() -> "Kardex":
    """Resolve the project layout and build the global configuration.

    This is deliberately *not* executed at import time. Importing
    ``navconfig`` -- or any of its submodules, ``navconfig.cli`` included --
    must never require a project to be scaffolded already: otherwise
    ``kardex env create``, the very command that creates ``env/``, could
    not run on a fresh checkout.

    Everything exported by this package (``config``, ``BASE_DIR``,
    ``DEBUG``, ...) triggers this function on first access, so regular
    consumers never need to call it explicitly. Call it directly only when
    you need the environment loaded into ``os.environ`` as a side effect
    without touching any of those names.

    Returns:
        Kardex: the global configuration container.
    """
    global _bootstrapped  # pylint: disable=W0603

    if _bootstrapped:
        return globals()["config"]

    ns = globals()

    # PROJECT PATH IS DEFINED?
    site_root, base_dir = project_root(__file__)
    ns["SITE_ROOT"] = site_root
    ns["BASE_DIR"] = base_dir

    ## Settings Directory
    settings_dir = base_dir.joinpath("settings")
    ns["SETTINGS_DIR"] = settings_dir

    # configuration of the environment type:
    env_type = get_env_type()
    ns["ENV_TYPE"] = env_type

    # ENV version (dev, prod, staging)
    ns["ENV"] = get_environment()

    # Loading main Configuration Object.
    cfg = Kardex(site_root, env=ns["ENV"], env_type=env_type)
    ns["config"] = cfg

    # DEBUG VERSION
    ns["DEBUG"] = cfg.debug
    ns["PRODUCTION"] = cfg.getboolean('PRODUCTION', fallback=not cfg.debug)
    # Environment
    ns["ENVIRONMENT"] = cfg.get('ENVIRONMENT', fallback='development')
    ns["ENV"] = cfg.get('ENV', fallback='dev')

    # Add Path Navigator to Sys path
    sys.path.append(str(base_dir))

    # Add Path settings to Sys path if exists.
    ensure_settings_priority(settings_dir)

    _bootstrapped = True
    return cfg


def __getattr__(name: str) -> Any:
    """Resolve the lazily-initialized package attributes (PEP 562)."""
    if name in _LAZY_NAMES:
        bootstrap()
        return globals()[name]
    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )


def __dir__() -> list:
    return sorted(set(globals()) | set(__all__))
