# Import Config Class
from navconfig import (
    BASE_DIR,
    config,
    DEBUG
)

file = BASE_DIR.joinpath('env', 'dev', '.prueba')
config.addEnv(file)

print(config.get('TEST'))
