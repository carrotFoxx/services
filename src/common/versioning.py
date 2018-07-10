from dataclasses import dataclass


@dataclass
class VersionedObject:
    version: int = 0
