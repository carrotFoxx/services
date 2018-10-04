import asyncio
import json
import logging
from asyncio import CancelledError

import pytest
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from common.consul import ConsulClient
from config import CONSUL_DSN
from supervisor import StateMonitor, Supervisor

logging.getLogger().removeHandler(logging.getLogger().handlers[0])

logger = logging.getLogger(__name__)

KAFKA_DSN = 'kafka:9092'


@pytest.fixture
async def supervisor(event_loop: asyncio.AbstractEventLoop) -> Supervisor:
    s = Supervisor(
        'python3', '/opt/project/src/supervisor/sample_process.py',
        state_monitor=StateMonitor(
            node_id='1',
            consul=ConsulClient(base=CONSUL_DSN, loop=event_loop),
            loop=event_loop
        ),
        loop=event_loop
    )
    yield s
    await s.stop()
    await s.state_monitor.consul.close()


async def produce(incoming_topic: str, amount: int, event_loop: asyncio.AbstractEventLoop):
    p = AIOKafkaProducer(loop=event_loop,
                         bootstrap_servers=KAFKA_DSN)
    await p.start()
    logger.info('stated producer')
    for x in range(0, amount):
        await p.send(topic=incoming_topic,
                     value=json.dumps({'seq': x, 'wsp': 'abcd', 'raw': ''}).encode())
        logger.info('send data: %s', x)
        if x % 10 == 0:
            await p.flush()

    await p.stop()
    logger.info('stopped producer')


async def consume(outgoing_topic: str, to: list, event_loop: asyncio.AbstractEventLoop):
    c = AIOKafkaConsumer(
        loop=event_loop,
        bootstrap_servers=KAFKA_DSN,
        # auto_offset_reset='earliest'
    )
    c.subscribe(topics=[outgoing_topic])
    try:
        await c.start()
        logger.info('started consumer')
        async for record in c:
            logger.info('received: %s', record.value.decode())
            to.append(record)
    except (CancelledError, GeneratorExit):
        raise
    finally:
        await c.stop()
        logger.info('stopped consumer')


@pytest.mark.asyncio
async def test_supervisor(supervisor: Supervisor, event_loop: asyncio.AbstractEventLoop):
    incoming_topic = 'events'
    outgoing_topic = 'correlations'
    supervisor._kafka_address = KAFKA_DSN

    control = []

    await supervisor._adopt({
        'incoming_stream': incoming_topic,
        'outgoing_stream': outgoing_topic
    })
    ct: asyncio.Task = event_loop.create_task(consume(outgoing_topic, to=control, event_loop=event_loop))
    await asyncio.sleep(1)
    event_loop.create_task(produce(incoming_topic, amount=10, event_loop=event_loop))
    await asyncio.sleep(5)
    ct.cancel()
    # await supervisor.stop()

    assert len(control) == 2
