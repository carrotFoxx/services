import attr

from common.versioning import VersionedObject
from config import KAFKA_DEFAULT_INCOMING_TOPIC, KAFKA_DEFAULT_OUTGOING_TOPIC, KAFKA_DEFAULT_PAUSE_STREAM
from mco.entities import ObjectBase, OwnedObject, RegisteredEntityJSONEncoder, TrackedObject
from microcore.entity.model import public_attributes
from microcore.storage.mongo import StorageEntityJSONEncoderBase


@attr.s(auto_attribs=True)
class App(VersionedObject, TrackedObject):
    name: str = None
    package: str = None  # indicate package used (Matlab, Hysys, TensorFlow, etc)
    description: str = None
    attachment: str = None
    environment: dict = attr.Factory(dict)


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


@attr.s(auto_attribs=True)
class Package(ObjectBase, OwnedObject, TrackedObject):
    name: str = None


class PackageJSONEncoder(RegisteredEntityJSONEncoder):
    entity_type = Package


@attr.s(auto_attribs=True)
class Model(VersionedObject, TrackedObject):
    name: str = None
    package: str = None  # indicate package it belongs to (Matlab, Hysys, TensorFlow, etc)
    description: str = None
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


@attr.s(auto_attribs=True)
class RouteConfig:
    wsp_uid: str

    desired_version: int = 0
    adopted_version: int = 0

    pause_stream: str = KAFKA_DEFAULT_PAUSE_STREAM


@attr.s(auto_attribs=True)
class RouteConfigConsumer(RouteConfig):
    incoming_stream: str = KAFKA_DEFAULT_INCOMING_TOPIC


class RouteConfigJSONEncoderConsumer(RegisteredEntityJSONEncoder):
    entity_type = RouteConfigConsumer


@attr.s(auto_attribs=True)
class RouteConfigProducer(RouteConfig):
    outgoing_stream: str = KAFKA_DEFAULT_OUTGOING_TOPIC


class RouteConfigJSONEncoderProducer(RegisteredEntityJSONEncoder):
    entity_type = RouteConfigProducer


@attr.s(auto_attribs=True)
class RouteConfigWorkspace(RouteConfig):
    incoming_stream: str = KAFKA_DEFAULT_INCOMING_TOPIC
    outgoing_stream: str = KAFKA_DEFAULT_OUTGOING_TOPIC


class RouteConfigJSONEncoderWorkspace(RegisteredEntityJSONEncoder):
    entity_type = RouteConfigWorkspace


@attr.s(auto_attribs=True)
class Workspace(ObjectBase, OwnedObject, TrackedObject):
    name: str = None

    type: str = None

    app_id: str = None
    app_ver: int = None

    model_id: str = None
    model_ver: str = None

    instance_id: str = None

    def preserve_from(self, other: 'Workspace'):
        super().preserve_from(other)
        self.uid = other.uid
        self.owner = other.owner


@attr.s(auto_attribs=True)
class WorkspaceNeighbors:
    incomingNeighbors: list = None
    outgoingNeighbors: list = None


class WorkspaceNeighborsJSONEncoder(RegisteredEntityJSONEncoder):
    entity_type = WorkspaceNeighbors


@attr.s(auto_attribs=True)
class WorkspacesChain:
    workspacesChainOutgoings: dict = None


@attr.s(auto_attribs=True)
class Chain(ObjectBase, OwnedObject, TrackedObject):
    name: str = None
    wr: list = None  # wsp + routes
    instance_id: str = None

    def preserve_from(self, other: 'Chain'):
        super().preserve_from(other)
        self.uid = other.uid
        self.owner = other.owner


class WorkspaceChainJSONEncoder(RegisteredEntityJSONEncoder):
    entity_type = WorkspacesChain


class WorkspaceJSONEncoder(RegisteredEntityJSONEncoder):
    entity_type = Workspace


class WorkspaceStorageEncoder(StorageEntityJSONEncoderBase):
    entity_type = Workspace


class ChainJSONEncoder(RegisteredEntityJSONEncoder):
    entity_type = Chain


class ChainStorageEncoder(StorageEntityJSONEncoderBase):
    entity_type = Chain


@attr.s(auto_attribs=True)
class Image(VersionedObject, TrackedObject):
    name: str = None

    app_id: str = None
    app_ver: int = None

    model_id: str = None
    model_ver: str = None

    description: str = None
    tags: list = None

    params: dict = attr.Factory(dict)


class ImageJSONEncoder(RegisteredEntityJSONEncoder):
    entity_type = Image


class ImageStorageEncoder(StorageEntityJSONEncoderBase):
    entity_type = Image


class ImageArchiveStorageEncoder(StorageEntityJSONEncoderBase):
    entity_type = Image

    @staticmethod
    def unpack(dct: dict, cls: type) -> object:
        dct.pop('_id', None)
        return cls(
            **dct
        )

    @staticmethod
    def pack(o: Image) -> dict:
        return {
            '_id': f'{o.uid}/{o.version}',
            **public_attributes(o)
        }
