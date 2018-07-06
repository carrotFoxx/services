from datetime import datetime

JSON_TYPE_FIELD = '__type__'
TYPE_SEPARATOR = '#'


def public_attributes(o: object, *, prefixes: set = {'_'}, exclude: set = None) -> dict:
    exclude: set = exclude or set()
    return {attr: getattr(o, attr) for attr in o.__dict__ if
            not attr.startswith(tuple(prefixes)) and attr not in exclude}


class EntityMixin:
    def map_fields_from_dict(self, dct: dict):
        for x, y in dct.items():
            if x == JSON_TYPE_FIELD:
                continue
            if hasattr(self, x):
                setattr(self, x, y)
            else:
                raise AttributeError('entity [%s] does not have field [%s]' % (self.__class__.__name__, x))

    @classmethod
    def from_dict(cls, dct: dict):
        obj = cls()
        obj.map_fields_from_dict(dct)

        return obj

    def preserve_from(self, donor: object):
        pass


class TimestampMixin:
    def __init__(self):
        super().__init__()
        self._ts = 0

    @property
    def timestamp(self):
        return self._ts

    @timestamp.setter
    def timestamp(self, value):
        if value is None:
            return
        if isinstance(value, datetime):
            self._ts = value.timestamp()
        elif isinstance(value, (int, float)):
            self._ts = value
        else:
            raise ValueError('unsupported value')
