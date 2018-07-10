import inject

from microcore.entity.encoders import ProxyNativeEncoder
from microcore.storage.mongo import SimpleMongoStorageAdapter, motor


class AppMongoStorageAdapter(SimpleMongoStorageAdapter):
    _encoder = inject.attr(ProxyNativeEncoder)

    def __init__(self) -> None:
        super().__init__(motor().buldozer.applications, self._encoder)
