# basic configuration of Logstash
import socket
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
        self.port = config.getint("LOGSTASH_PORT", fallback=self.port)

    def logstash_available(self, timeout=5):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            result = sock.connect_ex((self.host, int(self.port)))
        except TypeError:
            return False
        sock.close()
        return result == 0

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
