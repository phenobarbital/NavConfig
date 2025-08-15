from importlib import import_module
from .pyproject import pyProjectLoader


def import_loader(loader: str = "file"):
    classpath = f"navconfig.loaders.{loader}"
    cls = f"{loader}Loader"
    try:
        module = import_module(classpath, package="loaders")
        return getattr(module, cls)
    except ImportError as err:
        raise RuntimeError(f"Navconfig Error: Cannot load {cls}: {err}") from err
