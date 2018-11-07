from enum import Enum


class ProviderError(Exception):
    pass


class InstanceNotFound(ProviderError):
    pass


class ProviderKind(Enum):
    File = 'file'
    Docker = 'docker'
    VirtualMachine = 'vm'
