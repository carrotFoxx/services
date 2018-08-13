from typing import List

from mco.rpc import RPCRoutable
from .manager import ContainerManager


class ContainerManagerRPCAPI(RPCRoutable):
    def __init__(self, manager: ContainerManager) -> None:
        super().__init__()
        self.manager = manager

    def set_methods(self) -> List[callable]:
        return [
            self.manager.create_app_instance,
            self.manager.remove_app_instance
        ]
