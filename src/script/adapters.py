from common.entities import Chain, ChainStorageEncoder
from config import MONGO_DB
from microcore.entity.encoders import ProxyNativeEncoder
from microcore.storage.mongo import SimpleMongoStorageAdapter

_chain_encoder = ProxyNativeEncoder(
    force_type_mapping={
        Chain: ChainStorageEncoder()
    }
)

class ChainMongoStorageAdapter(SimpleMongoStorageAdapter):
    def __init__(self) -> None:
        super().__init__(MONGO_DB.chains, _chain_encoder)

    def save(self, entity: Chain):
        entity.date_update()
        return super().save(entity)

    def patch(self, entity: Chain, *args, **kwargs):
        entity.date_update()
        return super().patch(entity, *args, **kwargs)
