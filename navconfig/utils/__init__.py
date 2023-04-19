import sys
import os
from pathlib import Path, PurePath
# from inspect import getfile, currentframe


def is_virtualenv():
    if os.getenv('PYENV_VIRTUAL_ENV') or os.getenv('PYENV_VIRTUAL_ENV'):
        return True
    return (
        hasattr(sys, 'real_prefix') or (
            hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
    )


def project_root(base_file) -> PurePath:
    path = os.getenv('SITE_ROOT', None)
    # print(getfile(currentframe().f_back))
    if not path:
        if is_virtualenv():
            path = Path(sys.prefix).resolve().parent
        else:
            path = Path(os.path.abspath(os.path.dirname(base_file))).resolve().parent.parent
    if not path:
        path = Path(sys.prefix).resolve().parent
    if isinstance(path, str):
        path = Path(path)
    return path
