from container_manager import Provider
from container_manager.definitions import Instance, InstanceDefinition


class ContainerManager:
    def __init__(self, provider: Provider) -> None:
        self.provider = provider

    async def create_app_instance(self, definition: InstanceDefinition) -> Instance:
        return await self.provider.launch_instance(definition)

    async def remove_app_instance(self, definition: InstanceDefinition) -> bool:
        return await self.provider.remove_instance(definition)
