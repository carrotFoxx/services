import logging
from typing import Callable

from aiocache.backends.memory import SimpleMemoryBackend
from aiocache.base import BaseCache
from aiocache.serializers import NullSerializer

logger = logging.getLogger(__name__)


class ConfigurableMemoryBackend(SimpleMemoryBackend):
    def __init__(self, delete_handler: Callable, **kwargs):
        super().__init__(**kwargs)
        self.delete_handler = delete_handler

    # noinspection PyPep8Naming
    def _SimpleMemoryBackend__delete(self, key):
        """
        overrides parent class'es __delete method to add a hook
        """
        value = self.__class__._cache.pop(key, None)
        if value:
            handle = self.__class__._handlers.pop(key, None)
            if handle:
                handle.cancel()
            if self.delete_handler is not None:
                self.delete_handler(key, value)
            return 1

        return 0


class ConfigurableMemoryCache(ConfigurableMemoryBackend, BaseCache):
    def __init__(self, serializer=None, delete_handler: Callable = None, **kwargs):
        super().__init__(delete_handler=delete_handler, **kwargs)
        self.serializer = serializer or NullSerializer()
