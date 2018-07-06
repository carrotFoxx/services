from datetime import datetime, timezone
from enum import Enum
from typing import Union

from microcore.base.datetime import parse_datetime
from microcore.base.utils import FQN
from microcore.entity.encoders import JSONEncoderBase
from microcore.entity.model import EntityMixin, public_attributes


class StringEnum(Enum):
    def __str__(self):
        return self.value


class StringEnumEncoder(JSONEncoderBase):
    def default(self, o: object):
        if isinstance(o, StringEnum):
            return str(o)


class ObjectBase(EntityMixin):
    def __init__(self, uid: str = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.uid = uid

    def __repr__(self):
        return '<%s %s>' % (
            FQN.get_fqn(self),
            ', '.join([f'{attr}={value}' for attr, value in public_attributes(self).items()])
        )

    def __str__(self) -> str:
        return self.__repr__()

    def preserve_from(self, donor: 'ObjectBase'):
        super().preserve_from(donor)
        self.uid = donor.uid


class OwnedObject(EntityMixin):
    def __init__(self, owner: str = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.owner = owner

    def preserve_from(self, donor: 'OwnedObject'):
        super().preserve_from(donor)
        self.owner = donor.owner


DATETIME_STORAGE_FORMAT = '%Y-%m-%dT%H:%M:%S.%f'


class DateTimePropertyHelperMixin:
    @staticmethod
    def _issue_ts():
        return datetime.now(tz=timezone.utc)

    @staticmethod
    def _assign_ts(value) -> str:
        if isinstance(value, datetime):
            # utc+0: 2016-02-28T16:41:41.090123Z
            # utc+3: 2017-09-20T16:41:59.600123+03:00
            offset = value.strftime('%z')
            offset = offset[:3] + ':' + offset[3:] if value.utcoffset().seconds != 0 else 'Z'

            return value.strftime(DATETIME_STORAGE_FORMAT) + offset
        elif isinstance(value, str):
            return value
        else:
            raise ValueError('unsupported value')

    @staticmethod
    def _parse_ts(value) -> datetime:
        return parse_datetime(value)


class DatedObject(EntityMixin, DateTimePropertyHelperMixin):
    def __init__(self, **properties):
        self._ts = None
        super().__init__(**properties)

    @property
    def timestamp(self):
        return self._ts

    @timestamp.setter
    def timestamp(self, value):
        if value is None:
            return
        self._ts = self._assign_ts(value)

    def preserve_from(self, donor: 'DatedObject'):
        super().preserve_from(donor)
        self._ts = donor.timestamp


class TrackedObject(EntityMixin, DateTimePropertyHelperMixin):
    def __init__(self,
                 created: Union[str, datetime] = None,
                 updated: Union[str, datetime] = None,
                 **properties) -> None:
        super().__init__(**properties)
        self._created = None
        self._updated = None
        self.created = created or self._issue_ts()
        self.updated = updated or self.created

    @property
    def created(self):
        return self._created

    @created.setter
    def created(self, value):
        if self._created is not None:
            raise AttributeError('read only')
        self._created = self._assign_ts(value)

    @property
    def updated(self):
        return self._updated

    @updated.setter
    def updated(self, value):
        self._updated = self._assign_ts(value)

    def date_update(self):
        """
        dates the update fact, by writing current time to _update attribute
        """
        self.updated = self._issue_ts()

    def preserve_from(self, donor: 'TrackedObject'):
        super().preserve_from(donor)
        self._created = donor.created
