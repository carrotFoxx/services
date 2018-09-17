import asyncio
import logging
from asyncio import CancelledError
from typing import Awaitable, Callable, Dict, List

import aiokafka
import attr
from aiokafka import AIOKafkaConsumer, ConsumerRebalanceListener, ConsumerRecord, TopicPartition

from mco.utils import log_exceptions
from microcore.base.control import AsyncIOTaskManager

logger = logging.getLogger(__name__)


class PersistenceError(Exception):
    pass


class OffsetReporter(ConsumerRebalanceListener):

    async def on_partitions_revoked(self, revoked):
        logger.info('rebance occurred, committing offsets')
        logger.debug('revoked partitions, %s', revoked)
        await self.commit_offsets()

    def on_partitions_assigned(self, assigned):
        logger.info('rebance occured, new partions assigned: %s', assigned)

    def __init__(self, consumer: AIOKafkaConsumer) -> None:
        self._consumer = consumer
        self._offsets: Dict[TopicPartition, int] = {}

    def add_offset(self, key: TopicPartition, offset: int):
        self._offsets[key] = offset + 1

    async def commit_offsets(self):
        if len(self._offsets) == 0:
            return
        # copy and clear recorded offsets
        logger.debug('committing offsets: %s', self._offsets)
        await self._consumer.commit(self._offsets)
        self._offsets = {}


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
        self._tm = AsyncIOTaskManager(op_callback=self._task, loop=self._loop)

    def start(self) -> Awaitable:
        pass

    def stop(self) -> Awaitable:
        for x in self._tm:
            x.cancel()
        return asyncio.sleep(1)

    def add_consumer(self, topic: str, group_id: str, persist_func: Callable[[RecordBatchContainer], Awaitable]):
        logger.info('add consumer for topic=%s', topic)
        t = self._tm.add(topic, topic=topic, group_id=group_id, persist_func=persist_func)
        # this will relaunch task if it failed with exception (non-intentionally)
        t.add_done_callback(
            lambda fut: self._tm.add(
                hid=topic,
                topic=topic,
                group_id=group_id,
                persist_func=persist_func
            )
            if fut.exception() else None
        )

    def remove_consumer(self, topic: str):
        logger.info('removing consumer for topic=%s', topic)
        self._tm.remove(topic)

    def _create_consumer(self, group_id: str) -> (AIOKafkaConsumer, OffsetReporter):
        consumer = AIOKafkaConsumer(
            bootstrap_servers=self.servers,
            group_id=group_id,
            enable_auto_commit=False,
            fetch_min_bytes=64,
            max_partition_fetch_bytes=1024 * 1024 * 5,
            max_poll_records=1000,
            loop=self._loop
        )
        rebalance_listener = OffsetReporter(consumer=consumer)
        return consumer, rebalance_listener

    @log_exceptions
    async def _task(self, topic: str, group_id: str, persist_func: Callable[[RecordBatchContainer], Awaitable]):
        consumer, offset_mgr = self._create_consumer(group_id)
        try:
            consumer.subscribe(topics=[topic], listener=offset_mgr)
            await consumer.start()

            while True:
                try:
                    # todo: add reset to committed offsets on failures
                    # noinspection PyUnresolvedReferences
                    records = await consumer.getmany(max_records=500, timeout_ms=200)
                    if len(records) == 0:
                        await asyncio.sleep(1)
                        continue
                    await persist_func(RecordBatchContainer(records, offset_mgr))
                except PersistenceError:
                    logger.exception('failed persisting some of records')
                except aiokafka.errors.KafkaError:
                    logger.exception('consumer error')
                except CancelledError:
                    break
                finally:
                    await offset_mgr.commit_offsets()

        except aiokafka.errors.KafkaError:
            logger.exception('failed to start consumer')
            raise
        finally:
            await consumer.stop()
