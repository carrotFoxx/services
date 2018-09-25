import asyncio
import logging
from typing import Awaitable, Callable

import aiokafka
from aiokafka import AIOKafkaProducer

from mco.utils import convert_exceptions, log_exceptions
from microcore.base.control import AsyncIOTaskManager

logger = logging.getLogger(__name__)


class SamplingError(Exception):
    pass


class LoadGeneratorProducerManager:
    def __init__(self, servers: str, loop: asyncio.AbstractEventLoop = None) -> None:
        self.servers = servers
        self._loop = loop or asyncio.get_event_loop()
        self._tm = AsyncIOTaskManager(op_callback=self._task, loop=self._loop)

    def start(self) -> Awaitable:
        raise NotImplementedError

    def stop(self) -> Awaitable:
        for x in self._tm:
            x.cancel()
        return asyncio.sleep(1)

    def add_producer(self, topic: str, sampler_func: Callable[..., Awaitable]):
        # wrap sampler function to get expected exception type
        sampler_func = convert_exceptions(sampler_func, to=SamplingError)
        logger.info('add consumer for topic=%s', topic)
        t = self._tm.add(topic, topic=topic, sampler_func=sampler_func)
        # this will relaunch task if it failed with exception (non-intentionally)
        t.add_done_callback(
            lambda fut: self._tm.add(
                hid=topic,
                topic=topic,
                sampler_func=sampler_func
            )
            if fut.exception() else None
        )

    def _create_producer(self) -> AIOKafkaProducer:
        return AIOKafkaProducer(
            bootstrap_servers=self.servers,
            loop=self._loop
        )

    @log_exceptions
    async def _task(self, topic: str, sampler_func: Callable[..., Awaitable]):
        producer = self._create_producer()
        try:
            await producer.start()

            while True:
                try:
                    # sequenced value generator output to producer
                    await producer.send(
                        topic=topic,
                        value=await sampler_func()
                    )
                except SamplingError:
                    logger.exception('failed to sample a record')
                except aiokafka.errors.KafkaError:
                    logger.exception('producer error')
                except asyncio.CancelledError:
                    break

        except aiokafka.errors.KafkaError:
            logger.exception('failed to start producer')
            raise
        finally:
            await producer.stop()
