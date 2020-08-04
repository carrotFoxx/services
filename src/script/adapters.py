from common.entities import Manifest, ManifestStorageEncoder
from config import MONGO_DB
from microcore.entity.encoders import ProxyNativeEncoder
from microcore.storage.mongo import SimpleMongoStorageAdapter

_manifest_encoder = ProxyNativeEncoder(
    force_type_mapping={
        Manifest: ManifestStorageEncoder()
    }
)

class ManifestMongoStorageAdapter(SimpleMongoStorageAdapter):
    def __init__(self) -> None:
        super().__init__(MONGO_DB.manifests, _manifest_encoder)

    def save(self, entity: Manifest):
        entity.date_update()
        return super().save(entity)

    def patch(self, entity: Manifest, *args, **kwargs):
        entity.date_update()
        return super().patch(entity, *args, **kwargs)
