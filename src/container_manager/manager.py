from typing import Dict

from container_manager import Provider, ProviderKind
from container_manager.definitions import Instance, InstanceDefinition


class NoSuitableProviderEnabled(Exception):
    pass


class ContainerManager:
    def __init__(self, provider_map: Dict[ProviderKind, Provider]) -> None:
        self.providers = provider_map

    def _get_provider(self, referred_object: str) -> Provider:
        kind, _ = referred_object.split('://', 1)
        kind = ProviderKind(kind)
        if kind not in self.providers:
            raise NoSuitableProviderEnabled
        return self.providers[kind]

    async def create_app_instance(self, definition: InstanceDefinition) -> Instance:
        return await self._get_provider(definition.image).launch_instance(definition)

    async def remove_app_instance(self, definition: InstanceDefinition) -> bool:
        return await self._get_provider(definition.image).remove_instance(definition)
