import asyncio
from typing import Awaitable, Callable

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer, ConsumerRecord

from microcore.base.application import Application
from microcore.base.control import AsyncIOBackgroundManager


class _KafkaWrapperBase:
    _constructor: type = None

    def __init__(self, topic: str, *,
                 loop: asyncio.AbstractEventLoop = None, **kwargs) -> None:
        self.topic = topic
        self._loop = loop or asyncio.get_event_loop()
        self._interface = None
        self._config: dict = kwargs

    def _get_lo(self):
        if not self._interface:
            self._interface = self._constructor(**self._config, loop=self._loop)
        return self._interface

    def configure(self, **kwargs):
        self._config.update(kwargs)

    def start(self) -> Awaitable:
        return self._get_lo().start()

    async def stop(self):
        if not self._interface:
            return
        await self._interface.stop()


class Consumer(_KafkaWrapperBase):
    _constructor = AIOKafkaConsumer

    def __init__(self, loop: asyncio.AbstractEventLoop = None, **kwargs) -> None:
        super().__init__(loop=loop, **kwargs)
        self._on_message_cb = None
        self._tm = AsyncIOBackgroundManager(loop=self._loop)

    def configure(self, on_message: Callable[[ConsumerRecord], Awaitable], **kwargs):
        super().configure(**kwargs)
        self._on_message_cb = on_message

    async def _consumer_task(self):
        async for msg in self._interface:
            await self._on_message_cb(msg)

    def start(self) -> Awaitable:
        self._tm.add('consumer-loop', self._consumer_task())
        return super().start()

    def stop(self):
        self._tm.remove('consumer-loop')
        return super().stop()


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


class Producer(_KafkaWrapperBase):
    _constructor = AIOKafkaProducer

    async def publish(self, message: str, *, key=None):
        self._interface: AIOKafkaProducer
        await self._interface.send(topic=self.topic,
                                   value=message,
                                   key=key)
