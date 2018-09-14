import json
import logging
from typing import Dict, Iterator, List, Tuple, Union

from aiokafka import ConsumerRecord
from motor.core import AgnosticDatabase

from persistence.consumer import RecordBatchContainer

logger = logging.getLogger(__name__)


class MongoWriter:
    def __init__(self, db: AgnosticDatabase) -> None:
        self.db = db

    def _create_batch(self, iterator: Iterator, size: int = 100) -> Tuple[Dict[str, List[dict]], Union[int, None]]:
        batch: Dict[str, list] = {}
        last_offset = None
        for _ in range(size):
            try:
                record: ConsumerRecord = next(iterator)
                record_data: dict = json.loads(record.value)
                batch.setdefault(record_data['workspace'], [])
                batch[record_data['workspace']].append({
                    'data': str(record_data['raw_output']),
                    'timestamp': int(record_data['timestamp'])
                })
                last_offset = record.offset
            except StopIteration:
                break
        return batch, last_offset

    async def _persist_batch(self, batch: Dict[str, List[dict]]):
        pass

    async def process(self, record_batch: RecordBatchContainer):
        for tp, records in record_batch.records.items():
            iterator = iter(records)
            while True:
                batch, last_offset = self._create_batch(iterator, size=100)
                if last_offset is None:
                    break
                try:
                    await self._persist_batch(batch)
                    record_batch.report_offset(tp, last_offset)
                except Exception as e:
                    # todo: add retry
                    logger.exception('persistence failure')
