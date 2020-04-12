from common.entities import Image, ImageStorageEncoder, ImageArchiveStorageEncoder
from common.versioning import VersionedObject
from config import MONGO_DB
from microcore.entity.encoders import ProxyNativeEncoder
from microcore.storage.mongo import SimpleMongoStorageAdapter


class ImageMongoStorageAdapter(SimpleMongoStorageAdapter):
    _encoder = ProxyNativeEncoder(
        force_type_mapping={
            Image: ImageStorageEncoder()
        }
    )

    def __init__(self) -> None:
        super().__init__(MONGO_DB.images, self._encoder)

    def save(self, entity: Image):
        entity.date_update()
        return super().save(entity)


class ImageArchiveMongoStorageAdapter(SimpleMongoStorageAdapter):
    _encoder = ProxyNativeEncoder(
        force_type_mapping={
            Image: ImageArchiveStorageEncoder()
        }
    )

    @staticmethod
    def _primary_key(entity: VersionedObject):
        return f"{entity.uid}/{entity.version}"

    def __init__(self) -> None:
        super().__init__(MONGO_DB.images_archive, self._encoder)

