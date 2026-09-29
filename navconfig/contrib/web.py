from aiohttp import web
from navconfig import config, Kardex

class AiohttpConfig:
    def __init__(self, app: web.Application, key_name: str = 'config'):
        self.app = app
        config_key = web.AppKey(key_name, Kardex)
        if hasattr(self.app, key_name):
            # already configured
            return
        self.app[config_key] = config
        setattr(self.app, key_name, config)
