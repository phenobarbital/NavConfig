from .abstract import AbstractLog


class MailerHandler(AbstractLog):
    def __init__(self, config, loglevel, application) -> None:
        super().__init__(config, loglevel, application)
        self._admin = config.get(
            "logging_admin", section="logging", fallback="dev@domain.com"
        )
        self._email = config.get(
            "logging_email", section="logging", fallback="no-reply@domain.com"
        )
        self._mailhost = config.get(
            "logging_mail_host", section="logging", fallback="localhost"
        )

    def handler(self, **kwargs):
        hdlr = {
            "level": self.loglevel,
            "formatter": "error",
            "class": "logging.handlers.SMTPHandler",
            "mailhost": self._mailhost,
            "fromaddr": self._email,
            "toaddrs": [self._admin],
            "subject": f"Critical Error on {self.application}",
        }
        return hdlr
