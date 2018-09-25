import asyncio
import logging
from asyncio import CancelledError

import pytest

from sampling.generator import SampleRecordGenerator


@pytest.mark.asyncio
async def test_generator_amount():
    gen = SampleRecordGenerator(
        amount=10,
        delay=0.1
    )
    x = 0
    while x <= 10:
        try:
            item = await gen.generate()
        except CancelledError:
            break
        x += 1
        logging.info(item)

    assert x == 10


@pytest.mark.asyncio
async def test_generator_kill(event_loop: asyncio.AbstractEventLoop):
    gen = SampleRecordGenerator(
        amount=10,
        delay=0.2
    )

    async def wait_and_kill(delay: float):
        await asyncio.sleep(delay)
        gen.kill()

    event_loop.create_task(wait_and_kill(0.5))
    x = 0
    while x <= 10:
        try:
            item = await gen.generate()
        except CancelledError:
            break
        x += 1
        logging.info(item)

    assert x < 10
