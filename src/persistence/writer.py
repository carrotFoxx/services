import json
import logging
from typing import Dict, Iterator, List, Tuple, Union

import attr
from aiokafka import ConsumerRecord
from motor.core import AgnosticCollection, AgnosticDatabase
from pymongo.results import InsertManyResult

from mco.utils import convert_exceptions
from persistence.consumer import PersistenceError, RecordBatchContainer

logger = logging.getLogger(__name__)


@attr.s(auto_attribs=True)
class RecordData:
    workspace: str
    timestamp: int
    data: Union[str, list, dict] = None


class MongoWriter:
    def __init__(self, db: AgnosticDatabase) -> None:
        self.db = db

    @staticmethod
    def _decode_record(record: ConsumerRecord) -> RecordData:
        record_data: dict = json.loads(record.value)
        return RecordData(
            workspace=record_data['wsp'],
            timestamp=int(record_data['ts']),
            data=record_data['parsed']
            if 'parsed' in record_data and record_data['parsed'] is not None
            else record_data['raw']
        )

    def _create_batch(self, iterator: Iterator, size: int = 100) -> Tuple[Dict[str, List[dict]], Union[int, None]]:
        batch: Dict[str, list] = {}
        last_offset = None
        for _ in range(size):
            try:
                c_record: ConsumerRecord = next(iterator)
                record = self._decode_record(c_record)
                batch.setdefault(record.workspace, [])
                batch[record.workspace].append({
                    'data': record.data,
                    'ts': record.timestamp
                })
                last_offset = c_record.offset
            except StopIteration:
                break
        return batch, last_offset

    async def _persist_batch(self, batch: Dict[str, List[dict]]):
        for col_name, records in batch.items():
            collection: AgnosticCollection = self.db.get_collection('wsp_out_%s' % col_name.replace('-', ''))
            res: InsertManyResult = await collection.insert_many(records)
            inserted = len(res.inserted_ids)
            attempted = len(records)
            if inserted != attempted:
                raise PersistenceError('persisted only %s out of %s records', inserted, attempted)

    @convert_exceptions(to=PersistenceError)
    async def process(self, record_batch: RecordBatchContainer):
        errors = 0
        for tp, records in record_batch.records.items():
            iterator = iter(records)
            while True:
                batch, last_offset = self._create_batch(iterator, size=100)
                logger.info('persisting batch, offset: %s', last_offset)
                if last_offset is None:
                    break
                try:
                    await self._persist_batch(batch)
                    record_batch.report_offset(tp, last_offset)
                    logger.info('persisted offset: %s', last_offset)
                except:
                    # todo: add retry
                    logger.exception('persistence failure')
                    errors += 1
        if errors > 0:
            raise PersistenceError
