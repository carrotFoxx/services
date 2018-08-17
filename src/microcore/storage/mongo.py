import logging
import os
from typing import List, Tuple, Union

from motor.core import AgnosticCollection
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.results import DeleteResult, UpdateResult

from microcore.base.repository import DoesNotExist, Filter, StorageAdapter, StorageException
from microcore.entity.encoders import ProxyJSONEncoder, ProxyNativeEncoder, EntityJSONEncoderBase
from microcore.entity.model import public_attributes

logger = logging.getLogger(__name__)
MONGODB_DSN = os.getenv('MONGODB_DSN', 'mongodb://localhost:27017')
_client = AsyncIOMotorClient(MONGODB_DSN)


def motor() -> AsyncIOMotorClient:
    return _client


class SimpleMongoStorageAdapter(StorageAdapter):
    def __init__(self, collection: AgnosticCollection,
                 encoder: Union[ProxyJSONEncoder, ProxyNativeEncoder]) -> None:
        self._collection: AgnosticCollection = collection
        self._encoder: ProxyJSONEncoder = encoder

    @staticmethod
    def _primary_key(entity):
        return getattr(entity, 'uid')

    @property
    def native_interface(self) -> AgnosticCollection:
        return self._collection

    async def save(self, entity: object):
        result: UpdateResult = await self._collection.update_one(
            {'_id': self._primary_key(entity)},
            {'$set': self._encoder.default(entity)},
            upsert=True
        )
        result = result.matched_count == 1 or result.upserted_id == self._primary_key(entity)
        if not result:
            raise StorageException('Entity not saved')
        return True

    async def patch(self, entity: object, *, only: Tuple = None, exclude: Tuple = None, prop_filter: Filter = None):
        if only is not None and exclude is not None:
            raise ValueError('either only or exclude should be given, but not both')
        if (only is not None or exclude is not None) and prop_filter is not None:
            raise ValueError('either only/exclude or prop_filter should be given but not both')
        unfiltered = self._encoder.default(entity)
        prop_filter = prop_filter or Filter(only=only, exclude=exclude)
        filtered = prop_filter.filter(unfiltered)
        result: UpdateResult = await self._collection.update_one(
            {'_id': self._primary_key(entity)},
            {'$set': filtered},
            upsert=False
        )
        result = result.matched_count == 1
        if not result:
            raise StorageException('Entity not patched')
        return True

    @staticmethod
    def _extract_sort_argument(properties) -> Union[List[Tuple[str, int]], None]:
        sort = properties.pop('_sort', None)
        if sort is not None:
            if not isinstance(sort, dict):
                raise ValueError('_sort must be a dict of fields and sort order like:`{field:<1|-1>,...}`')
            sort = list(sort.items())
        return sort

    @staticmethod
    def _extract_limit_argument(properties):
        return properties.pop('_limit', 100)

    async def find(self, properties: dict = None) -> List:
        properties = properties or {}
        lst = []
        limit = self._extract_limit_argument(properties)
        sort = self._extract_sort_argument(properties)
        cursor = self._collection.find(properties, sort=sort, limit=limit)
        async for document in cursor:
            lst.append(self._encoder.decoder_object_hook(document))
        return lst

    async def find_one(self, eid=None, **kwargs) -> object:
        document = await self._load_existing(eid, **kwargs)
        if not document:
            raise DoesNotExist('entity with [_id:%s] does not exist in mongo:collection[%s]'
                               % (eid, self._collection.name))
        return document

    async def exists(self, eid, **kwargs):
        if eid is not None:
            kwargs['_id'] = eid
        return (await self._collection
                .find(kwargs, projection=False)
                .limit(1)
                .count(with_limit_and_skip=True)) == 1

    async def load(self, eid) -> object:
        if eid is None:
            raise ValueError('cant load unidentified document: eid should not be None')
        document = await self._load_existing(eid)
        if not document:
            raise DoesNotExist('entity with [_id:%s] does not exist in mongo:collection[%s]'
                               % (eid, self._collection.name))
        return document

    async def _load_existing(self, eid=None, **kwargs) -> Union[object, None]:
        if eid is not None:
            kwargs['_id'] = eid
        sort = self._extract_sort_argument(kwargs)
        document = await self._collection.find_one(kwargs, sort=sort)
        if not document:
            return None
        return self._encoder.decoder_object_hook(document)

    async def delete(self, eid):
        await self.load(eid)
        res: DeleteResult = await self._collection.delete_one({'_id': eid})
        if res.deleted_count == 1:
            return True
        raise StorageException('failed to delete')

    async def delete_many(self, properties: dict):
        res: DeleteResult = await self._collection.delete_many(properties)
        return res.deleted_count


class StorageEntityJSONEncoderBase(EntityJSONEncoderBase):

    @staticmethod
    def unpack(dct: dict, cls: type) -> object:
        return cls(
            uid=dct.pop('_id'),
            **dct
        )

    @staticmethod
    def pack(o: object) -> dict:
        return {
            '_id': getattr(o, 'uid'),
            **public_attributes(o, exclude={'uid'})
        }
