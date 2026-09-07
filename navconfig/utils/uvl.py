import sys


def install_uvloop() -> None:
    """Lazily install uvloop when available on a supported platform."""
    if sys.platform == "win32":
        return

    try:
        import uvloop  # noqa # pylint: disable=import-outside-toplevel
    except ImportError:
        return

    uvloop.install()
