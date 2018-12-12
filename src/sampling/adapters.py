from datetime import datetime

import attr
from marshmallow.utils import from_iso_datetime, isoformat

from config import MONGO_DB
from mco.entities import DatedObject, ObjectBase, OwnedObject, RegisteredEntityJSONEncoder
from microcore.entity.encoders import ProxyNativeEncoder
from microcore.entity.model import public_attributes
from microcore.storage.mongo import SimpleMongoStorageAdapter, StorageEntityJSONEncoderBase


@attr.s(auto_attribs=True)
class Retrospective(ObjectBase, OwnedObject, DatedObject):
    name: str = None
    start: datetime = None
    end: datetime = None
    query: dict = attr.Factory(dict)
    src_collection: str = None
    dst_topic: str = None
    running: bool = None


class RetrospectiveJSONEncoder(RegisteredEntityJSONEncoder):
    entity_type = Retrospective

    @staticmethod
    def unpack(dct: dict, cls: type) -> entity_type:
        try:
            return cls(
                start=from_iso_datetime(dct.pop('start', None)),
                end=from_iso_datetime(dct.pop('end', None)),
                **dct
            )
        except KeyError as e:
            raise AttributeError from e

    @staticmethod
    def pack(o: Retrospective) -> dict:
        dct = attr.asdict(o) if attr.has(type(o)) else public_attributes(o)
        dct['start'] = isoformat(o.start) if o.start is not None else None
        dct['end'] = isoformat(o.end) if o.end is not None else None
        if o.running is not None:
            dct['running'] = o.running
        else:
            del dct['running']
        return dct


class RetrospectiveStorageEncoder(StorageEntityJSONEncoderBase):
    entity_type = Retrospective


class RetrospectiveMongoStorageAdapter(SimpleMongoStorageAdapter):
    _encoder = ProxyNativeEncoder(
        force_type_mapping={
            Retrospective: RetrospectiveStorageEncoder()
        }
    )

    def __init__(self) -> None:
        super().__init__(MONGO_DB.op_retrospectives, self._encoder)
