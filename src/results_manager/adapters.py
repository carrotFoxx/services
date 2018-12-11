from typing import Any, Union

import attr
from motor.core import AgnosticCollection

from mco.entities import DatedObject, ObjectBase, RegisteredEntityJSONEncoder
from microcore.storage.mongo import SimpleMongoStorageAdapter, StorageEntityJSONEncoderBase


@attr.s(auto_attribs=True)
class Record(ObjectBase, DatedObject):
    data: Any = None


class RecordStorageEncoder(StorageEntityJSONEncoderBase):
    entity_type = Record

    @staticmethod
    def pack(o: Record) -> dict:
        return {
            '_id': o.uid,
            'data': o.data,
            'ts': o.timestamp
        }

    @staticmethod
    def unpack(dct: dict, cls: type) -> object:
        return cls(
            uid=str(dct.pop('_id')),
            data=dct['data'],
            timestamp=dct['ts']
        )

    def default(self, o: object) -> dict:
        if isinstance(o, self.entity_type):
            dct = self.pack(o)
            return dct
        return super().default(o)

    @classmethod
    def decoder_object_hook(cls, dct: dict) -> Union[dict, entity_type]:
        return cls.unpack(dct, cls.entity_type)


class RecordJSONEncoder(RegisteredEntityJSONEncoder):
    entity_type = Record


class RecordMongoStorageAdapter(SimpleMongoStorageAdapter):
    _encoder = RecordStorageEncoder()  # a lil bit hacky but actually interfaces are compatible so it is fine

    def __init__(self, collection: AgnosticCollection) -> None:
        super().__init__(collection, self._encoder)
