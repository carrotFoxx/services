from dataclasses import dataclass

from common.versioning import VersionedObject
from mco.entities import ObjectBase, OwnedObject, RegisteredEntityJSONEncoder, TrackedObject


@dataclass
class App(ObjectBase, OwnedObject, VersionedObject, TrackedObject):
    name: str = None
    package: str = None  # indicate package used (Matlab, Hysys, TensorFlow, etc)
    description: str = None


class AppJSONEncoder(RegisteredEntityJSONEncoder):
    entity_type = App


@dataclass
class Package(ObjectBase, OwnedObject, TrackedObject):
    name: str = None


class PackageJSONEncoder(RegisteredEntityJSONEncoder):
    entity_type = Package


@dataclass
class Model(ObjectBase, OwnedObject, VersionedObject, TrackedObject):
    package: str = None


class ModelJSONEncoder(RegisteredEntityJSONEncoder):
    entity_type = Model
