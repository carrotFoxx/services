import asyncio
import functools
import inspect
import logging
from typing import Any, Awaitable, List

import inject
from aiohttp_json_rpc import JsonRpc, JsonRpcClient, RpcGenericServerDefinedError, RpcInvalidParamsError, \
    RpcInvalidRequestError
from aiohttp_json_rpc.communicaton import JsonRpcRequest

from microcore.base.application import WebApplication
from microcore.entity.encoders import ProxyNativeEncoder

logger = logging.getLogger(__name__)


class RPCRoutable:
    def set_methods(self) -> List[callable]:
        raise NotImplementedError


class RPCServerApplication(WebApplication):
    async def _setup(self):
        await super()._setup()
        self.rpc_setup = JsonRpc()
        self.server.router.add_route('*', '/', self.rpc_setup)

    def add_methods_from(self, routable: RPCRoutable):
        self.add_methods(routable.set_methods())

    def add_methods(self, methods: List[callable]):
        methods = [
            ('', rpc_expose(method)) for method in methods
        ]
        self.rpc_setup.add_methods(*methods)


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

    async def _request(self, *args, method: str, rpc_timeout=1, **kwargs) -> Any:
        if len(args) > 0 and len(kwargs) > 0:
            raise RpcInvalidParamsError('params should be either positional or key-value, but not both')
        params = list(args) or kwargs
        params = self._encoder.dump(params)
        response = await self._client.call(method=method, params=params, timeout=rpc_timeout)
        return self._encoder.load(response)

    def close(self) -> Awaitable:
        return self._client.disconnect()


@inject.params(encoder=ProxyNativeEncoder)
def rpc_expose(method: callable, encoder: ProxyNativeEncoder, name=None):
    if getattr(method, '_is_rpc_exposed', False):
        return method

    signature = inspect.Signature.from_callable(method, follow_wrapped=False)

    async def _dispatch(request: JsonRpcRequest):
        try:
            params = encoder.load(request.params)
            if isinstance(params, dict):
                matched: inspect.BoundArguments = signature.bind(**params)
            else:
                matched: inspect.BoundArguments = signature.bind(*params)
        except TypeError as e:
            raise RpcInvalidParamsError from e
        except Exception as e:
            raise RpcInvalidRequestError from e
        try:
            return await method(*matched.args, **matched.kwargs)
        except Exception as e:
            logger.exception('rpc method generic exception')
            raise RpcGenericServerDefinedError(
                data=str(e),
                error_code=-32005,
                message='Server failed to fulfill request'
            ) from e

    _dispatch.__name__ = name or method.__name__
    _dispatch._is_rpc_exposed = True

    return _dispatch
