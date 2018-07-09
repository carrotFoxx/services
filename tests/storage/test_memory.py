import asyncio
from unittest import TestCase
from unittest.mock import Mock

from aiocache.backends.memory import SimpleMemoryBackend

from microcore.storage.memory import ConfigurableMemoryCache
from tests import run_async


class TestConfigurableMemoryCache(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.memory = ConfigurableMemoryCache()

    @run_async
    async def test_1_set(self):
        await self.memory.set('test', 123, ttl=5)
        self.assertIn('test', SimpleMemoryBackend._cache)
        self.assertIn('test', SimpleMemoryBackend._handlers)

    @run_async
    async def test_2_sync_delete_handler(self):
        handler = Mock()
        self.memory.delete_handler = handler
        await self.memory.set('test', 123, ttl=1)
        await asyncio.sleep(2)
        handler.assert_called_with('test', 123)

    @run_async
    async def test_3_async_delete_handler(self):
        handler = Mock()

        async def _coro(key, value):
            return handler(key, value)

        def _handler(key, value):
            asyncio.get_event_loop().create_task(_coro(key, value))

        self.memory.delete_handler = _handler
        await self.memory.set('test', 123, ttl=1)
        await asyncio.sleep(2)
        handler.assert_called_with('test', 123)
