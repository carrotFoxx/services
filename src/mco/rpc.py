import asyncio
import functools
from typing import Any, Awaitable

from aiohttp_json_rpc import JsonRpc, JsonRpcClient

from microcore.base.application import WebApplication
from microcore.entity.encoders import ProxyNativeEncoder


class RPCRoutable:
    def set_routes(self, router: JsonRpc):
        raise NotImplementedError


class RPCServerApplication(WebApplication):
    async def _setup(self):
        await super()._setup()
        self.rpc_setup = JsonRpc()
        self.server.router.add_route('*', '/', self.rpc_setup)

    def add_routes_from(self, routable: RPCRoutable):
        routable.set_routes(self.rpc_setup)


class RPCClient:
    def __init__(self, server_url: str, encoder: ProxyNativeEncoder, *, loop=None) -> None:
        super().__init__()
        self._encoder = encoder
        self._loop = loop or asyncio.get_event_loop()
        self._client = JsonRpcClient(url=server_url, loop=self._loop)

    def __getattribute__(self, name: str) -> Any:
        if name.startswith('_') or name == 'close':
            return super().__getattribute__(name)
        return functools.partial(self._request, method=name)

    async def _request(self, method, *, rpc_timeout=-1, **kwargs) -> Any:
        kwargs = self._encoder.dump(kwargs)
        response = await self._client.call(method=method, params=kwargs, timeout=rpc_timeout)
        return self._encoder.load(response)

    def close(self) -> Awaitable:
        return self._client.disconnect()
