import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import List

import pytest
from aiokafka import AIOKafkaProducer
from motor.core import AgnosticCollection

from config import KAFKA_DSN
from microcore.storage.mongo import motor
from persistence.consumer import PersistenceConsumerManager, RecordBatchContainer
from persistence.writer import MongoWriter

WSP_ID = str(uuid.uuid4().hex)

logger = logging.getLogger()


def create_entry(x: int):
    return {
        'wsp': WSP_ID,
        'raw': str(x),
        'ts': int(datetime.now().timestamp() * 1000)
    }


async def produce(incoming_topic: str, amount: int, event_loop: asyncio.AbstractEventLoop):
    p = AIOKafkaProducer(loop=event_loop,
                         bootstrap_servers=KAFKA_DSN)
    await p.start()
    logger.info('stated producer')
    for x in range(0, amount):
        await p.send(topic=incoming_topic,
                     value=json.dumps(create_entry(x)).encode())
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


@pytest.fixture
async def mongo_writer(event_loop: asyncio.AbstractEventLoop) -> MongoWriter:
    w = MongoWriter(
        db=motor().test_db
    )
    yield w

    await motor().drop_database(w.db)


@pytest.mark.asyncio
async def test_mongo_writer(event_loop: asyncio.AbstractEventLoop,
                            persistence_manager: PersistenceConsumerManager,
                            mongo_writer: MongoWriter):
    persistence_manager.add_consumer(
        topic='persisted_events',
        group_id='test_1',
        persist_func=mongo_writer.process
    )

    await asyncio.sleep(2)
    await produce('persisted_events', amount=100, event_loop=event_loop)
    await asyncio.sleep(5)

    collection: AgnosticCollection = mongo_writer.db.get_collection('wsp_out_%s' % WSP_ID)
    count = await collection.count_documents({})
    assert count == 100
