import asyncio
import json
import logging
import os
from typing import Any, Awaitable

import aioredis

from microcore.base.repository import DoesNotExist, StorageAdapter, StorageException
from microcore.entity.encoders import ProxyJSONEncoder

logger = logging.getLogger(__name__)

REDIS_DSN = os.getenv('REDIS_DSN', 'redis://localhost:6379/1')


class Redis:
    def __init__(self, dsn: str, loop=None, **kwargs) -> None:
        super().__init__()
        self._loop = loop or asyncio.get_event_loop()
        self.dsn = dsn
        self.options = {'encoding': 'utf-8', **kwargs}
        self._redis: aioredis.Redis = None

    async def _open(self, dsn: str, **kwargs):
        logger.info('creating connection pool')
        self._redis = await aioredis.create_redis_pool(dsn, **kwargs)

    async def __aenter__(self):
        if self._redis is None:
            await self._open(self.dsn, **self.options)
        return self._redis

    async def __aexit__(self, exc_type=None, exc_val=None, exc_tb=None):
        if isinstance(exc_type, aioredis.RedisError):
            logger.warning('redis error in context [%s]', exc_val)
        return False

    def close(self) -> Awaitable:
        """
        this function is a coroutine
        """
        logger.info('closing connection pool, waiting to be closed')
        self._redis.close()
        return self._redis.wait_closed()


_redis_instance = Redis(dsn=REDIS_DSN, db=1, minsize=5)


def setup_redis(redis_instance: Redis):
    global _redis_instance
    _redis_instance = redis_instance


def redis():
    return _redis_instance


class SimpleRedisStorageAdapter(StorageAdapter):
    def __init__(self, encoder: ProxyJSONEncoder, key_prefix: str = None,
                 expire: int = 0, redis_instance: Redis = None) -> None:
        self._redis: Redis = redis_instance or redis()
        self._encoder: ProxyJSONEncoder = encoder
        self._key_prefix = key_prefix
        self._expire = expire

    def _key(self, eid: str):
        return self._key_prefix + eid

    @staticmethod
    def _primary_key(entity):
        return getattr(entity, 'uid')

    def _decode(self, data: str):
        try:
            return json.loads(data, object_hook=self._encoder.decoder_object_hook)
        except (TypeError, AssertionError) as e:
            raise StorageException() from e

    def _encode(self, data: Any):
        return json.dumps(data, default=self._encoder.default)

    async def load(self, eid):
        async with self._redis as r:
            data = await r.get(self._key(eid))
        if not data:
            raise DoesNotExist()
        return self._decode(data)

    async def save(self, entity):
        async with self._redis as r:
            data = self._encode(entity)
            await r.set(self._key(self._primary_key(entity)), data, expire=self._expire)

    async def delete(self, eid):
        async with self._redis as r:
            return await r.delete(self._key(eid))
