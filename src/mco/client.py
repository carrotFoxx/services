import asyncio
import contextlib
import logging
from copy import copy
from typing import Awaitable

from aiohttp import ClientError, ClientResponse, ClientSession, hdrs
from marshmallow import ValidationError

logger = logging.getLogger(__name__)


class HTTPClient:
    class InteractionError(Exception):
        pass

    def __init__(self, base: str, default_headers: dict = None, default_params: dict = None,
                 client: ClientSession = None, loop: asyncio.AbstractEventLoop = None) -> None:
        super().__init__()
        self._base = base
        self.default_headers = default_headers or {hdrs.CONTENT_TYPE: 'application/json'}
        self.default_params = default_params or {}
        self._loop = loop or asyncio.get_event_loop()
        self._client = client or ClientSession(loop=self._loop)

    def close(self) -> Awaitable:
        return self._client.close()

    def _url(self, path: str, base: str = None) -> str:
        base = base or self._base
        return base.rstrip('/') + '/' + path.lstrip('/')

    def _req(self, path, params: dict = None, headers: dict = None, base: str = None) -> dict:
        params = params or {}
        headers = headers or {}
        client_args = {
            'url': self._url(path, base=base),
            'params': {**self.default_params, **params},
            'headers': {**self.default_headers, **headers}
        }
        logger.debug('request args:\n%s', client_args)
        return client_args

    @contextlib.contextmanager
    def with_options(self, headers: dict = None, params: dict = None):
        headers = headers or {}
        params = params or {}
        context_instance = copy(self)
        context_instance.default_headers = {**self.default_headers, **headers}
        context_instance.default_params = {**self.default_params, **params}
        try:
            yield context_instance
        finally:
            del context_instance

    @staticmethod
    async def _data(response: ClientResponse) -> dict:
        logger.info('requested: [%s %s %s]', response.method, response.status, response.url)
        if 400 <= response.status:
            logger.info('response: %s', await response.text())
        response.raise_for_status()
        json = await response.json()
        logger.info('response: %s', json)
        return json

    @staticmethod
    async def _status(response: ClientResponse, status=(200, 201, 202, 204)):
        logger.info('requested: [%s %s]', response.method, response.url)
        logger.info('response: %s', await response.text())
        if response.status not in status:
            response.raise_for_status()
        return True


def error_handler(fn):
    async def catcher(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except (ValidationError, ClientError) as e:
            raise args[0].__class__.InteractionError from e

    return catcher
