from dataclasses import asdict, dataclass, field, is_dataclass
from uuid import uuid4

from microcore.entity.abstract import Identifiable, Owned, Preserver
from microcore.entity.bases import DateTimePropertyHelperMixin
from microcore.entity.encoders import RegisteredEntityJSONEncoderBase
from microcore.entity.model import public_attributes


@dataclass
class ObjectBase(Identifiable):
    uid: str = field(default_factory=lambda: uuid4().hex)

    def get_uid(self):
        return self.uid

    def set_uid(self, value: str):
        self.uid = value


@dataclass
class OwnedObject(Owned):
    owner: str = None

    def get_owner(self):
        return self.owner

    def set_owner(self, value: str):
        self.owner = value


@dataclass
class DatedObject(DateTimePropertyHelperMixin):
    timestamp: float = None

    def __post_init__(self):
        self.timestamp = self.timestamp or self._issue_ts().timestamp()


@dataclass
class TrackedObject(DateTimePropertyHelperMixin, Preserver):
    created: float = None
    updated: float = None

    def preserve_from(self, other: 'TrackedObject'):
        super().preserve_from(other)
        self.created = other.created

    def date_update(self):
        """
        dates the update fact, by writing current time to _update attribute
        """
        self.updated = self._issue_ts().timestamp()

    def __post_init__(self):
        self.created = self.created or self._issue_ts().timestamp()
        self.updated = self.updated or self.created


class RegisteredEntityJSONEncoder(RegisteredEntityJSONEncoderBase):
    entity_type = 0x01

    @staticmethod
    def pack(o) -> dict:
        if is_dataclass(o):
            return asdict(o)
        return public_attributes(o)
