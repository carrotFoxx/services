from dataclasses import dataclass

from common.versioning import VersionedObject
from mco.entities import ObjectBase, OwnedObject, RegisteredEntityJSONEncoder, TrackedObject
from microcore.entity.model import public_attributes
from microcore.storage.mongo import StorageEntityJSONEncoderBase


@dataclass
class App(VersionedObject, TrackedObject):
    name: str = None
    package: str = None  # indicate package used (Matlab, Hysys, TensorFlow, etc)
    description: str = None
    attachment: str = None


class AppJSONEncoder(RegisteredEntityJSONEncoder):
    entity_type = App


class AppStorageEncoder(StorageEntityJSONEncoderBase):
    entity_type = App


class AppArchiveStorageEncoder(StorageEntityJSONEncoderBase):
    entity_type = App

    @staticmethod
    def unpack(dct: dict, cls: type) -> object:
        dct.pop('_id', None)
        return cls(
            **dct
        )

    @staticmethod
    def pack(o: App) -> dict:
        return {
            '_id': f'{o.uid}/{o.version}',
            **public_attributes(o)
        }


@dataclass
class Package(ObjectBase, OwnedObject, TrackedObject):
    name: str = None


class PackageJSONEncoder(RegisteredEntityJSONEncoder):
    entity_type = Package


@dataclass
class Model(VersionedObject, TrackedObject):
    name: str = None
    package: str = None  # indicate package it belongs to (Matlab, Hysys, TensorFlow, etc)
    attachment: str = None


class ModelJSONEncoder(RegisteredEntityJSONEncoder):
    entity_type = Model


class ModelStorageEncoder(StorageEntityJSONEncoderBase):
    entity_type = Model


class ModelArchiveStorageEncoder(StorageEntityJSONEncoderBase):
    entity_type = Model

    @staticmethod
    def unpack(dct: dict, cls: type) -> object:
        dct.pop('_id', None)
        return cls(
            **dct
        )

    @staticmethod
    def pack(o: App) -> dict:
        return {
            '_id': f'{o.uid}/{o.version}',
            **public_attributes(o)
        }
