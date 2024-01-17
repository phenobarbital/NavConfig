import logging
from .abstract import AbstractLog


class FileHandler(AbstractLog):
    def handler(self, path: str, loglevel=None, **kwargs):
        if loglevel is None:
            loglevel = self.loglevel
        if loglevel == logging.ERROR:
            filename = {"filename": f"{path}/{self._logname}.error.log"}
        else:
            filename = {"filename": f"{path}/{self._logname}.log"}
        hdlr = {
            "class": "logging.handlers.RotatingFileHandler",
            "maxBytes": (1048576 * 5),
            "backupCount": 2,
            "encoding": "utf-8",
            "formatter": "file",
            "level": loglevel,
            **filename,
        }
        return hdlr
