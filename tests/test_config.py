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
    from settings.settings import LOCAL_DEVELOPMENT as LP
    assert LP == LOCAL_DEVELOPMENT
    dictConfig(logging_config)
    log = logging.getLogger()
    log.debug('HELLO WORLD')

async def test_environment(event_loop):
    from navconfig import config
    config.configure(env='dev', override=True)  # re-configure the environment
    cnf = config.get('CONFIG_FILE')
    assert cnf == 'etc/navigator.ini'

async def test_settings(event_loop):
    from navconfig import config
    from settings.settings import SEND_NOTIFICATIONS
    assert SEND_NOTIFICATIONS is True

async def test_local_settings(event_loop):
    from navconfig import config
    from navconfig.conf import CONFIG_TEST
    from settings.settings import CONFIG_TEST as CT
    ct = config.get('CONFIG_TEST', fallback='NAVCONFIG')
    assert ct == CT
    assert CONFIG_TEST == CT


def pytest_sessionfinish(session, exitstatus):
    asyncio.get_event_loop().close()
