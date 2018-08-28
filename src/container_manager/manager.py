from container_manager.definition import Instance, InstanceDefinition
from container_manager.docker import DockerProvider


class ContainerManager:
    def __init__(self, provider: DockerProvider) -> None:
        self.provider = provider

    async def create_app_instance(self, definition: InstanceDefinition) -> Instance:
        return await self.provider.launch_instance(definition)

    async def remove_app_instance(self, definition: InstanceDefinition) -> bool:
        return await self.provider.remove_instance(definition)
