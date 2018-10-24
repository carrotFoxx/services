from abc import ABC, abstractmethod
from typing import Awaitable

from container_manager.definitions import Instance, InstanceDefinition


class ProviderError(Exception):
    pass


class InstanceNotFound(ProviderError):
    pass


class Provider(ABC):
    @abstractmethod
    def create_instance(self, definition: InstanceDefinition) -> Awaitable[Instance]:
        pass

    @abstractmethod
    def launch_instance(self, definition: InstanceDefinition) -> Awaitable[Instance]:
        pass

    @abstractmethod
    def stop_instance(self, definition: InstanceDefinition) -> Awaitable[bool]:
        pass

    @abstractmethod
    def remove_instance(self, definition: InstanceDefinition) -> Awaitable[bool]:
        pass
