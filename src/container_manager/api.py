import inject
from aiohttp_json_rpc import JsonRpc
from aiohttp_json_rpc.communicaton import JsonRpcRequest

from mco.rpc import RPCRoutable
from microcore.entity.encoders import ProxyNativeEncoder
from .manager import ContainerManager


class ContainerManagerRPCAPI(RPCRoutable):
    _encoder = inject.attr(ProxyNativeEncoder)

    def __init__(self, manager: ContainerManager) -> None:
        super().__init__()
        self.manager = manager

    def _decode(self, request: JsonRpcRequest):
        return self._encoder.load(request.params)

    def set_routes(self, router: JsonRpc):
        router.add_methods(
            ('', self._decor(self.manager.create_app_instance)),
            ('', self._decor(self.manager.remove_app_instance)),
        )

    def _decor(self, method: callable):
        async def _dispatch(request: JsonRpcRequest):
            params = self._decode(request)
            return await method(**params)

        _dispatch.__name__ = method.__name__

        return _dispatch
