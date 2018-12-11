import attr

from config import MONGO_DB
from mco.entities import DatedObject, ObjectBase, OwnedObject, RegisteredEntityJSONEncoder
from microcore.entity.encoders import ProxyNativeEncoder
from microcore.storage.mongo import SimpleMongoStorageAdapter, StorageEntityJSONEncoderBase


@attr.s(auto_attribs=True)
class Retrospective(ObjectBase, OwnedObject, DatedObject):
    name: str = None
    query: dict = attr.Factory(dict)
    src_collection: str = None
    dst_topic: str = None


class RetrospectiveJSONEncoder(RegisteredEntityJSONEncoder):
    entity_type = Retrospective


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
