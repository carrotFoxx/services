from typing import Awaitable

from container_manager import Instance, InstanceDefinition, Provider


class KubernetesProvider(Provider):

    def create_instance(self, definition: InstanceDefinition) -> Awaitable[Instance]:
        pass

    def launch_instance(self, definition: InstanceDefinition) -> Awaitable[Instance]:
        pass

    def stop_instance(self, definition: InstanceDefinition) -> Awaitable[bool]:
        pass

    def remove_instance(self, definition: InstanceDefinition) -> Awaitable[bool]:
        pass
