from common.entities import App, AppArchiveStorageEncoder, AppStorageEncoder
from common.versioning import VersionedObject
from config import MONGO_DB
from microcore.entity.encoders import ProxyNativeEncoder
from microcore.storage.mongo import SimpleMongoStorageAdapter


class AppMongoStorageAdapter(SimpleMongoStorageAdapter):
    _encoder = ProxyNativeEncoder(
        force_type_mapping={
            App: AppStorageEncoder()
        }
    )

    def __init__(self) -> None:
        super().__init__(MONGO_DB.applications, self._encoder)


class AppArchiveMongoStorageAdapter(SimpleMongoStorageAdapter):
    _encoder = ProxyNativeEncoder(
        force_type_mapping={
            App: AppArchiveStorageEncoder()
        }
    )

    @staticmethod
    def _primary_key(entity: VersionedObject):
        return f"{entity.uid}/{entity.version}"

    def __init__(self) -> None:
        super().__init__(MONGO_DB.applications_archive, self._encoder)
