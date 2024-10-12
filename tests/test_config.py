import pytest
import os
import logging
from logging.config import dictConfig
import asyncio
from pathlib import Path
import pytest_asyncio
from navconfig.logging import logging_config


pytestmark = pytest.mark.asyncio
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

async def test_config(event_loop):
    # os.environ["DEBUG"] = 'True'  # Force Set Debug to TRUE
    from navconfig import config, SITE_ROOT, BASE_DIR, DEBUG
    current_path = Path(__file__).resolve().parent.parent
    assert current_path == SITE_ROOT
    debug = bool(os.getenv('DEBUG', False))
    assert debug == DEBUG


async def test_conf(event_loop):
    from navconfig import config
    from navconfig.conf import LOCAL_DEVELOPMENT
    assert LOCAL_DEVELOPMENT == False
    dictConfig(logging_config)
    log = logging.getLogger()
    log.debug('HELLO WORLD')

async def test_environment(event_loop):
    from navconfig import config
    config.configure(env='dev', override=True)  # re-configure the environment
    cnf = config.get('CONFIG_FILE')
    assert cnf == 'etc/navigator.ini'

def pytest_sessionfinish(session, exitstatus):
    asyncio.get_event_loop().close()
