import asyncio
import logging
from asyncio import CancelledError
from typing import Union

import pytest
from motor.core import AgnosticClient
from motor.motor_asyncio import AsyncIOMotorClient

from sampling.generator import MongoRecordGenerator, SampleRecordGenerator


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

    _ = event_loop.create_task(wait_and_kill(0.5))
    x = 0
    while x <= 10:
        try:
            item = await gen.generate()
        except CancelledError:
            break
        x += 1
        logging.info(item)

    assert x < 10


@pytest.mark.asyncio
async def test_mongo_generator(event_loop: asyncio.AbstractEventLoop):
    client: Union[AgnosticClient, AsyncIOMotorClient] = AsyncIOMotorClient('mongodb://10.0.0.12:30017',
                                                                           io_loop=event_loop)
    d = await MongoRecordGenerator(collection=client.events.cef).generate()
    logging.info('generated doc: %s', d)
