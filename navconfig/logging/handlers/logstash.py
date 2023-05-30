# basic configuration of Logstash
try:
    import logstash_async  # pylint: disable=W0611
except ImportError as ex:
    raise RuntimeError(
        "NavConfig: Logstash Logging is enabled but Logstash async \
            dependency is not installed.\
        Hint: run 'pip install logstash_async'."
    ) from ex


class LogstashHandler:
    def __init__(self, config) -> None:
        self.env = config.ENV if config.ENV is not None else 'production'
        self.host = config.get('LOGSTASH_HOST', fallback='127.0.0.1')
        self.port = config.getint('LOGSTASH_PORT', fallback=6000)

    def formatter(
            self,
            application: str,
            path: str,
            fqdn: bool = False,
            **kwargs
    ):
        return {
            '()': 'logstash_async.formatter.LogstashFormatter',
            'message_type': 'python-logstash',
            'fqdn': fqdn,
            "extra_prefix": 'dev',
            'extra': {
                'application': f'{application}',
                'project_path': f'{path}',
                'environment': self.env,
                **kwargs
            }
        }

    def handler(self, loglevel, enable_localdb: bool = False, **kwargs):
        hdlr = {
            'class': 'logstash_async.handler.AsynchronousLogstashHandler',
            'formatter': 'logstash',
            'transport': 'logstash_async.transport.TcpTransport',
            'host': self.host,
            'port': int(self.port),
            'level': loglevel
        }
        if enable_localdb is True:
            log_dir = kwargs['logdir']
            hdlr['database_path'] = f'{log_dir}/logstash.db'
        else:
            hdlr['database_path'] = ''
        if 'propagate' in kwargs:
            hdlr['propagate'] = kwargs['propagate']
        return hdlr
