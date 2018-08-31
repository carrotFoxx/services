import asyncio
import json
import logging
from asyncio import CancelledError

import pytest
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from common.consul import ConsulClient
from config import CONSUL_DSN
from supervisor import StateMonitor, Supervisor

logger = logging.getLogger(__name__)

KAFKA_DSN = 'kafka:9092'


@pytest.fixture(scope='module')
async def supervisor(event_loop: asyncio.AbstractEventLoop) -> Supervisor:
    s = Supervisor(
        'cat',
        state_monitor=StateMonitor(
            node_id='1',
            consul=ConsulClient(base=CONSUL_DSN, loop=event_loop),
            loop=event_loop
        ),
        loop=event_loop
    )
    yield s
    # await s.stop()


@pytest.mark.asyncio
async def test_supervisor(supervisor: Supervisor, event_loop: asyncio.AbstractEventLoop):
    incoming_topic = 'events'
    outgoing_topic = 'correlations'
    supervisor._kafka_address = KAFKA_DSN

    async def produce():
        p = AIOKafkaProducer(loop=event_loop,
                             bootstrap_servers=KAFKA_DSN)
        await p.start()
        logger.info('stated producer')
        for x in range(1, 10):
            await p.send(topic=incoming_topic,
                         value=json.dumps({'id': x}).encode())
            logger.info('send data: %s', x)
            if x % 10 == 0:
                await p.flush()

        await p.stop()
        logger.info('stopped producer')

    async def consume():
        c = AIOKafkaConsumer(
            loop=event_loop,
            bootstrap_servers=KAFKA_DSN,
            # auto_offset_reset='earliest'
        )
        c.subscribe(topics=[outgoing_topic])
        try:
            c.start()
            logger.info('started producer')
            async for record in c:
                logger.info('received: %s', record.value.decode())
        except (CancelledError, GeneratorExit):
            raise
        finally:
            await c.stop()
            logger.info('stopped producer')

    await supervisor._adopt({
        'incoming_stream': incoming_topic,
        'outgoing_stream': outgoing_topic
    })
    await asyncio.sleep(1)
    event_loop.create_task(produce())
    ct: asyncio.Task = event_loop.create_task(consume())
    await asyncio.sleep(10)
    ct.cancel()
    await asyncio.sleep(1)
    await supervisor.stop()
