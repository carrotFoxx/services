import abc
import os
from typing import Type

from container_manager import ProviderKind, REF_SPLIT_TOKEN


class Attachment(abc.ABC):
    _kind: Type[ProviderKind]

    def __init__(self, definition: str) -> None:
        super().__init__()
        self.kind: ProviderKind
        self.path: str
        kind, path = definition.split(REF_SPLIT_TOKEN, 1)
        self.kind = ProviderKind(kind)
        self.path = path

        if self.kind is not self._kind:
            raise ValueError('invalid attachment type')

    @abc.abstractmethod
    def absolute(self) -> str:
        pass


class FileAttachment(Attachment):
    _kind = ProviderKind.File

    def __init__(self, definition: str, mount_path: str) -> None:
        super().__init__(definition)
        self.mount_path = mount_path

    def absolute(self) -> str:
        return os.path.join(self.mount_path, self.path)
