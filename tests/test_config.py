import os
import logging
import asyncio
import pytest
import pytest_asyncio
from pathlib import Path
from pprint import pprint
from asyncdb import AsyncDB

pytestmark = pytest.mark.asyncio


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


def pytest_sessionfinish(session, exitstatus):
    asyncio.get_event_loop().close()
