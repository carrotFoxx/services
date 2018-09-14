import asyncio
import logging
from typing import Awaitable, Dict, List

import aiokafka
import attr
from aiokafka import AIOKafkaConsumer, ConsumerRebalanceListener, ConsumerRecord
from kafka import TopicPartition

from microcore.base.control import AsyncIOBackgroundManager

logger = logging.getLogger(__name__)


class PersistenceError(Exception):
    pass


class OffsetReporter(ConsumerRebalanceListener):

    def on_partitions_revoked(self, revoked) -> Awaitable:
        logger.info('rebance occurred, committing offsets')
        logger.debug('revoked partitions, %s', revoked)
        return self.commit_offsets()

    def on_partitions_assigned(self, assigned):
        logger.info('rebance occured, new partions assigned: %s', assigned)

    def __init__(self, consumer: AIOKafkaConsumer) -> None:
        self._consumer = consumer
        self._offsets: Dict[TopicPartition, int] = {}

    def add_offset(self, key: TopicPartition, offset: int):
        self._offsets[key] = offset + 1

    def commit_offsets(self) -> Awaitable:
        # copy and clear recorded offsets
        offsets = self._offsets
        self._offsets = {}
        return self._consumer.commit(offsets)


@attr.s(auto_attribs=True)
class RecordBatchContainer:
    records: Dict[TopicPartition, List[ConsumerRecord]]
    _offset_manager: OffsetReporter

    def report_offset(self, key: TopicPartition, offset: int):
        self._offset_manager.add_offset(key, offset)


class PersistenceConsumerManager:

    def __init__(self, servers: str, loop: asyncio.AbstractEventLoop = None) -> None:
        self.servers = servers
        self._loop = loop or asyncio.get_event_loop()
        self._tm = AsyncIOBackgroundManager(loop=self._loop)

    def start(self) -> Awaitable:
        pass

    def stop(self) -> Awaitable:
        pass

    def _create_consumer(self) -> (AIOKafkaConsumer, OffsetReporter):
        consumer = AIOKafkaConsumer(bootstrap_servers=self.servers, loop=self._loop, enable_auto_commit=False)
        rebalance_listener = OffsetReporter(consumer=consumer)
        return consumer, rebalance_listener

    async def task(self, topic: str, persist_func: callable):
        try:
            consumer, offset_mgr = self._create_consumer()
            consumer.subscribe(topics=[topic], listener=offset_mgr)
            await consumer.start()
        except aiokafka.errors.KafkaError:
            logger.exception('failed to start consumer')
            raise

        while True:
            try:
                # noinspection PyUnresolvedReferences
                records = await consumer.getmany(max_records=500, timeout_ms=200)
                # todo: check if empty and wait
                await persist_func(RecordBatchContainer(records, offset_mgr))
                await offset_mgr.commit_offsets()
            except PersistenceError:
                logger.exception('failed persisting some of records')
            except aiokafka.errors.KafkaError:
                logger.exception('consumer error')
            finally:
                await offset_mgr.commit_offsets()
                await consumer.stop()
