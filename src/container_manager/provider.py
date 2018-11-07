from abc import ABC, abstractmethod
from typing import Awaitable

from container_manager.definitions import Instance, InstanceDefinition
from container_manager.attachment import ImageAttachment

LABEL_PREFIX = 'com.buldozer.'


class Provider(ABC):
    ORCHESTRATOR_ID: str = 'undefined'

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

    @classmethod
    def _normalize_labels(cls, dct: dict):
        return {
            **{LABEL_PREFIX + key: str(value) for key, value in dct.items() if not key.startswith(LABEL_PREFIX)},
            **{key: str(value) for key, value in dct.items() if key.startswith(LABEL_PREFIX)},
            LABEL_PREFIX + 'project': 'buldozer',
            LABEL_PREFIX + 'provider': cls.ORCHESTRATOR_ID
        }

    @staticmethod
    def _extract_image(ref: str) -> str:
        return ImageAttachment(ref).absolute()


