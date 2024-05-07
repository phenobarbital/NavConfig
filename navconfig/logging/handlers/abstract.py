from abc import ABCMeta


class AbstractLog(metaclass=ABCMeta):
    """AbstractLog.

    Abstract class for Logger Handlers.
    """

    def __init__(self, config, loglevel, application: str) -> None:
        self.env = config.ENV if config.ENV is not None else "production"
        self.loglevel = loglevel
        self.application = application
        self.host = config.get(
            "logging_host", section="logging", fallback="localhost"
        )
        self.port = config.getint(
            "logging_port", section="logging", fallback=9600
        )
        # log name:
        self._logname = config.get(
            "logname", section="logging", fallback=application
        )
