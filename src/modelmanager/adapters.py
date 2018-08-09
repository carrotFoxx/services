from common.entities import Model, ModelArchiveStorageEncoder, ModelStorageEncoder
from common.versioning import VersionedObject
from config import MONGO_DB
from microcore.entity.encoders import ProxyNativeEncoder
from microcore.storage.mongo import SimpleMongoStorageAdapter


class ModelMongoStorageAdapter(SimpleMongoStorageAdapter):
    _encoder = ProxyNativeEncoder(
        force_type_mapping={
            Model: ModelStorageEncoder()
        }
    )

    def __init__(self) -> None:
        super().__init__(MONGO_DB.models, self._encoder)

    def save(self, entity: Model):
        entity.date_update()
        return super().save(entity)


class ModelArchiveMongoStorageAdapter(SimpleMongoStorageAdapter):
    _encoder = ProxyNativeEncoder(
        force_type_mapping={
            Model: ModelArchiveStorageEncoder()
        }
    )

    @staticmethod
    def _primary_key(entity: VersionedObject):
        return f"{entity.uid}/{entity.version}"

    def __init__(self) -> None:
        super().__init__(MONGO_DB.models_archive, self._encoder)
