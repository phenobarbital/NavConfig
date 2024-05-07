import sys
import os
from pathlib import Path, PurePath

def get_environment() -> str:
    """Returns the environment selected."""
    return os.getenv("ENV", "")


def get_env_type() -> str:
    # environment type can be a file (.env) an encrypted file (crypt)
    return os.getenv("ENV_TYPE", "file")


def is_virtualenv() -> bool:
    return (
        os.getenv("PYENV_VIRTUAL_ENV") or os.getenv("PYENV_VIRTUAL_ENV")
        or hasattr(sys, "real_prefix")
        or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix)
    )

def is_notebook() -> bool:
    try:
        from IPython import get_ipython  # pylint: disable=import-outside-toplevel
        if 'IPKernelApp' not in get_ipython().config:  # pragma: no cover
            return False
        return True
    except ImportError:
        return False
    except AttributeError:
        return False

def find_project_root(
    base_file: str,
    markers=("etc/config.ini", ".env")
) -> PurePath:
    current_dir = Path(base_file).resolve().parent
    for marker in markers:
        for parent in current_dir.parents:
            if (parent / marker).exists():
                return parent
    return current_dir


def project_root(base_file: str) -> PurePath:
    site_root = os.getenv("SITE_ROOT", None)
    base_dir = os.getenv("BASE_DIR", None)
    if site_root is not None:
        site_root = Path(site_root).resolve()
    else:
        if is_virtualenv():
            site_root = Path(sys.prefix).resolve().parent
        else:
            site_root = find_project_root(base_file)

    if base_dir is None:
        base_dir = site_root
    else:
        base_dir = Path(base_dir).resolve()

    return site_root, base_dir
