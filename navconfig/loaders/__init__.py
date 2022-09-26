from importlib import import_module


def import_loader(loader: str = 'file'):
    classpath = f"navconfig.loaders.{loader}"
    cls = f"{loader}Loader"
    try:
        module = import_module(classpath, package="loaders")
        obj = getattr(module, cls)
        return obj
    except ImportError as err:
        raise RuntimeError(
            f"Navconfig Error: Cannot load {cls}: {err}"
        ) from err
