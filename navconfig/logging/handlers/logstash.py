# basic configuration of Logstash
try:
    import logstash_async  # pylint: disable=W0611
except ImportError as ex:
    raise RuntimeError(
        "NavConfig: Logstash Logging is enabled but Logstash async \
            dependency is not installed.\
        Hint: run 'pip install logstash_async'."
    ) from ex
from .abstract import AbstractLog


class LogstashHandler(AbstractLog):
    """LogstashHandler.

    Send Logs to Logstash using Logstash-async.
    """

    def __init__(self, config, loglevel, application: str) -> None:
        super(LogstashHandler, self).__init__(config, loglevel, application)
        self._flush_timeout = config.getint(
            "logstash_flush_timeout", section="logging", fallback=10
        )
        self.host = config.get("LOGSTASH_HOST", fallback=self.host)
        self.port = config.get("LOGSTASH_PORT", fallback=self.port)

    def formatter(self, path: str, fqdn: bool = False, **kwargs):
        return {
            "()": "logstash_async.formatter.LogstashFormatter",
            "message_type": "python-logstash",
            "fqdn": fqdn,
            "extra_prefix": "dev",
            "extra": {
                "application": f"{self.application}",
                "project_path": f"{path}",
                "environment": self.env,
                **kwargs,
            },
        }

    def handler(self, enable_localdb: bool = False, **kwargs):
        hdlr = {
            "class": "logstash_async.handler.AsynchronousLogstashHandler",
            "formatter": "logstash",
            "transport": "logstash_async.transport.TcpTransport",
            "transport_type": "tcp",
            "host": self.host,
            "port": int(self.port),
            "flush_timeout": self._flush_timeout,  # set the flush_timeout
            "level": self.loglevel,
        }
        if enable_localdb is True:
            log_dir = kwargs["logdir"]
            hdlr["database_path"] = f"{log_dir}/logstash.db"
        else:
            hdlr["database_path"] = ""
        if "propagate" in kwargs:
            hdlr["propagate"] = kwargs["propagate"]
        return hdlr
