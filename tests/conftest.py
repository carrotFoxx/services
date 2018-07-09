import asyncio
from types import SimpleNamespace

import pytest


@pytest.fixture(scope='module')
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope='module')
def context():
    ctx = SimpleNamespace()
    yield ctx
    del ctx
