import sys
import os
from pathlib import Path, PurePath

def is_virtualenv():
    return (
        hasattr(sys, 'real_prefix') or (
            hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
    )

def project_root(base_file) -> PurePath:
    path = os.getenv('SITE_ROOT', None)
    if not path:
        if is_virtualenv():
            path = Path(sys.prefix).resolve().parent
        else:
            path = Path(os.path.abspath(os.path.dirname(base_file))).resolve().parent.parent
    if not path:
        path = Path(sys.prefix).resolve().parent
    return path
