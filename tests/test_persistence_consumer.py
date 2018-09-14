import asyncio
import json
import logging
from typing import List

import pytest
from aiokafka import AIOKafkaProducer

from config import KAFKA_DSN
from persistence.consumer import PersistenceConsumerManager, RecordBatchContainer

logger = logging.getLogger()


async def produce(incoming_topic: str, amount: int, event_loop: asyncio.AbstractEventLoop):
    p = AIOKafkaProducer(loop=event_loop,
                         bootstrap_servers=KAFKA_DSN)
    await p.start()
    logger.info('stated producer')
    for x in range(0, amount):
        await p.send(topic=incoming_topic,
                     value=json.dumps({'id': x}).encode())
        logger.info('send data: %s', x)
        if x % 10 == 0:
            await p.flush()

    await p.stop()
    logger.info('stopped producer')


@pytest.fixture
async def persistence_manager(event_loop: asyncio.AbstractEventLoop) -> PersistenceConsumerManager:
    pm = PersistenceConsumerManager(
        servers=KAFKA_DSN,
        loop=event_loop
    )
    yield pm

    await pm.stop()


@pytest.mark.asyncio
async def test_consumer(event_loop, persistence_manager: PersistenceConsumerManager):
    received: List[RecordBatchContainer] = []

    async def persist_check(rb: RecordBatchContainer):
        logger.info('got batch: %s', id(rb))
        received.append(rb)
        [rb.report_offset(tp, records[-1].offset) for tp, records in rb.records.items()]

    persistence_manager.add_consumer(
        topic='events',
        group_id='test_1',
        persist_func=persist_check
    )
    await asyncio.sleep(2)
    await produce('events', 100, event_loop)
    await asyncio.sleep(5)

    assert len(received) > 0
    total_received = 0
    for b in received:
        total_received += sum([len(records) for records in b.records.values()])
    assert total_received == 100
