import abc
import os
from enum import Enum
from typing import Type

from container_manager import ProviderKind

REF_SPLIT_TOKEN = '://'


class AttachmentPrefix(Enum):
    File = ProviderKind.File.value + REF_SPLIT_TOKEN
    Docker = ProviderKind.Docker.value + REF_SPLIT_TOKEN
    VirtualMachine = ProviderKind.VirtualMachine.value + REF_SPLIT_TOKEN

    @staticmethod
    def check(value: str) -> ProviderKind:
        """
        try extracting provider from attachment
        :param value:
        :return: ProviderKind
        :raises ValueError if provider does not exists
        """
        k, _ = value.split(REF_SPLIT_TOKEN, 1)
        return ProviderKind(k)


class Attachment(abc.ABC):
    _kind: Type[ProviderKind]

    def __init__(self, definition: str) -> None:
        super().__init__()
        kind, path = definition.split(REF_SPLIT_TOKEN, 1)
        self.kind: ProviderKind = ProviderKind(kind)
        self.path: str = path
        if not self._check():
            raise ValueError('invalid attachment type')

    def _check(self):
        return self.kind is self._kind

    @abc.abstractmethod
    def absolute(self) -> str:
        pass

    def provider(self) -> ProviderKind:
        return self.kind


class FileAttachment(Attachment):
    _kind = ProviderKind.File

    def __init__(self, definition: str, mount_path: str) -> None:
        super().__init__(definition)
        self.mount_path = mount_path

    def absolute(self) -> str:
        return os.path.join(self.mount_path, self.path)


class ImageAttachment(Attachment):
    _kind = (ProviderKind.Docker, ProviderKind.VirtualMachine)

    def _check(self):
        return self.kind in self._kind

    def absolute(self) -> str:
        return self.path
