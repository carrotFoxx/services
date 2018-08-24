import asyncio
from typing import Awaitable, Callable

from aiokafka import AIOKafkaConsumer, ConsumerRecord

from microcore.base.application import Application
from microcore.base.control import AsyncIOBackgroundManager


class Consumer:
    def __init__(self, loop: asyncio.AbstractEventLoop = None, **kwargs) -> None:
        self._loop = loop or asyncio.get_event_loop()
        self._consumer: AIOKafkaConsumer = None
        self._consumer_config: dict = kwargs
        self._on_message_cb = None
        self._tm = AsyncIOBackgroundManager(loop=self._loop)

    def _get_lo(self) -> AIOKafkaConsumer:
        if not self._consumer:
            self._consumer = AIOKafkaConsumer(**self._consumer_config, loop=self._loop)
        return self._consumer

    def configure(self, on_message: Callable[[ConsumerRecord], Awaitable], **kwargs):
        self._consumer_config.update(kwargs)
        self._on_message_cb = on_message

    async def _consumer_task(self):
        async for msg in self._consumer:
            await self._on_message_cb(msg)

    async def start(self):
        await self._get_lo().start()
        self._tm.add('consumer-loop', self._consumer_task())

    async def stop(self):
        if not self._consumer:
            return
        await self._consumer.stop()
        self._tm.remove('consumer-loop')


class ConsumerWorker(Application):

    def __init__(self, consumer: Consumer, **kwargs):
        super().__init__(**kwargs)
        self.consumer = consumer

    def _init_consumer(self):
        self.consumer.configure(on_message=self.on_message)
        self.consumer.start()

    async def on_message(self, msg: ConsumerRecord):
        raise NotImplementedError

    async def _setup(self):
        await super()._setup()
        await self._init_consumer()

    async def _shutdown(self):
        await self.consumer.stop()
        await super()._shutdown()
