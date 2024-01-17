import sys
import os
from pathlib import Path, PurePath


def is_virtualenv() -> bool:
    if os.getenv("PYENV_VIRTUAL_ENV") or os.getenv("PYENV_VIRTUAL_ENV"):
        return True
    return hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    )


def project_root(base_file: str) -> PurePath:
    path = os.getenv("SITE_ROOT", None)
    if path:
        return Path(path)

    if is_virtualenv():
        return Path(sys.prefix).resolve().parent

    # Resolve the directory of the base_file
    path = Path(base_file).resolve().parent.parent

    if not path:
        path = Path(sys.prefix).resolve().parent
    if isinstance(path, str):
        path = Path(path)
    return path
