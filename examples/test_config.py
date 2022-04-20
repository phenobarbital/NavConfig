# Import Config Class
from navconfig import (
    BASE_DIR,
    config,
    DEBUG
)
from navconfig.logging import (
    logging
)

"""
Routes
"""
APP_NAME = config.get('APP_NAME', fallback='Navigator')
APP_DIR = BASE_DIR.joinpath("apps")

logging.debug(f'::: STARTING APP: {APP_NAME} in path: {APP_DIR} ::: ')
print(f'STARTING WITH DEBUG: {DEBUG}')

PRODUCTION  = config.get('PRODUCTION')
ALLOWED_HOSTS = [
    e.strip()
    for e in list(config.get("ALLOWED_HOSTS", section="auth", fallback="localhost*").split(","))
]
print(f'Allowed HOSTS: {ALLOWED_HOSTS}')
print(f'Production: {PRODUCTION}')