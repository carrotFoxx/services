import asyncio
import logging
import signal
from asyncio import CancelledError
from pprint import pformat

import aiokafka.errors
import inject
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer, ConsumerRecord

from microcore.base.control import AsyncIOBackgroundManager
from supervisor.state import StateMonitor

logger = logging.getLogger(__name__)


class Supervisor:
    consul = inject.attr('consul')

    def __init__(self,
                 program: str, *args,
                 state_monitor: StateMonitor,
                 loop: asyncio.AbstractEventLoop = None) -> None:
        super().__init__()
        self.program = program
        self.program_args = args
        self._loop = loop or asyncio.get_event_loop()

        self._process: asyncio.subprocess.Process = None
        self._tm = AsyncIOBackgroundManager(loop=self._loop)
        self._rq = asyncio.Queue()
        self._wq = asyncio.Queue()

        self._kafka_address: str = None
        self.state_monitor = state_monitor

    _ENGINE = 'engine'
    _KAFKA_READER = 'kafka_reader'
    _KAFKA_WRITER = 'kafka_writer'

    async def _adopt(self, data: dict):
        logger.info('adopted config...\b%s', pformat(data))
        read_topic = data.get('incoming_stream')
        write_topic = data.get('outgoing_stream')
        # close previous
        engine = self._tm.get(self._ENGINE)
        if engine is not None:
            self._tm.remove(self._KAFKA_READER)
            await asyncio.sleep(1)
            self._tm.remove(self._PIPE_WRITER)
            await asyncio.sleep(1)
            self._tm.remove(self._PIPE_READER)
            await asyncio.sleep(1)
            self._tm.remove(self._KAFKA_WRITER)
            await asyncio.sleep(1)
            self._process.send_signal(signal.SIGTERM)
            await engine

        self._tm.add(self._ENGINE, self._engine_controller())
        self._tm.add(self._KAFKA_READER, self._kafka_consumer(read_topic))
        self._tm.add(self._KAFKA_WRITER, self._kafka_producer(write_topic))

    _STATE_MONITOR = 'state_monitor'

    async def start(self):
        self.state_monitor.adoption_cb = self._adopt
        self._tm.add(self._STATE_MONITOR, self.state_monitor.task())

    async def stop(self):
        self._tm.remove(self._STATE_MONITOR)
        self._tm.remove(self._KAFKA_READER)
        self._tm.remove(self._PIPE_WRITER)
        self._tm.remove(self._PIPE_READER)
        self._tm.remove(self._KAFKA_WRITER)
        if self._process:
            self._process.send_signal(signal.SIGTERM)
            await self._tm.get(self._ENGINE)
        else:
            self._tm.remove(self._ENGINE)
        return await asyncio.sleep(2)

    async def _get_kafka_address(self) -> str:
        if not self._kafka_address:
            # todo: resolve via consul
            self._kafka_address = 'localhost:9092'
        return self._kafka_address

    async def _kafka_consumer(self, topic: str):
        logger.info('init consumer->rq')
        consumer = AIOKafkaConsumer(
            loop=self._loop,
            bootstrap_servers=await self._get_kafka_address(),
            # auto_offset_reset='earliest'
        )

        try:
            consumer.subscribe(topics=[topic])
            await consumer.start()
            logger.info('started consumer->rq')
            async for record in consumer:  # type: ConsumerRecord
                await self._rq.put(record.value)
                logger.info('received record: %s', record.value.decode())
        except (aiokafka.errors.KafkaError,
                aiokafka.errors.TopicAuthorizationFailedError,
                aiokafka.errors.OffsetOutOfRangeError) as e:
            logger.exception('while consuming from topic=%s', topic)
        finally:
            await consumer.stop()
            logger.info('stopped consumer->rq')

    async def _kafka_producer(self, topic: str):
        logger.info('init wq->producer')
        producer = AIOKafkaProducer(
            loop=self._loop,
            bootstrap_servers=await self._get_kafka_address()
        )

        try:
            await producer.start()
            logger.info('started wq->producer')
            while True:
                record = await self._wq.get()
                await producer.send(topic=topic, value=record)
                logger.info('sent record: %s', record)
        except (aiokafka.errors.KafkaError,
                aiokafka.errors.TopicAuthorizationFailedError,
                aiokafka.errors.RecordTooLargeError) as e:
            logger.exception('while producing to topic=%s', topic)
        finally:
            await producer.stop()
            logger.info('stopped wq->producer')

    _PIPE_WRITER = 'pipe_writer'
    _PIPE_READER = 'pipe_reader'

    async def _engine_controller(self):
        process: asyncio.subprocess.Process = await asyncio.create_subprocess_exec(
            program=self.program, *self.program_args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=2 ** 20  # 1MiB
        )
        self._process = process
        self._tm.add(self._PIPE_WRITER, self._engine_writer(process.stdin))
        self._tm.add(self._PIPE_READER, self._engine_reader(process.stdout))
        await process.wait()

    async def _engine_writer(self, stream_writer: asyncio.StreamWriter):
        logger.info('starting PIPE writer')
        while True:
            try:
                record: bytes = await self._rq.get()
                stream_writer.write(record+'\n'.encode())
                logger.info('pushed to PIPE')
                await stream_writer.drain()
            except (CancelledError, GeneratorExit):
                logger.info('closing PIPE writer')
                stream_writer.write_eof()
                stream_writer.close()
                raise
            except:
                logger.exception('unexpected exception while writing to PIPE')

    async def _engine_reader(self, stream_reader: asyncio.StreamReader):
        logger.info('starting PIPE reader')
        while True:
            try:
                record: str = await stream_reader.readline()
                logger.info('received from PIPE: %s', record)
                await self._wq.put(record)
            except (CancelledError, GeneratorExit):
                logger.info('closing PIPE reader')
                raise
            except:
                logger.exception('unexpected exception while reading from PIPE')
