from typing import Tuple


class Filter:
    def __init__(self, *, only: Tuple = None, exclude: Tuple = None) -> None:
        super().__init__()
        self._only = only or ()
        self._exclude = exclude or ()

    @staticmethod
    def _intersect(left: set, right: set):
        return left & right

    @staticmethod
    def _diff(left: set, right: set):
        return left - right

    def filter(self, dct: dict):
        original = set(dct.keys())
        if self._only:  # leave only given fields
            fields = self._intersect(original, set(self._only))
        elif self._exclude:
            fields = self._diff(original, set(self._exclude))
        else:
            return dct

        filtered = {}
        for x in fields:
            filtered[x] = dct[x]
        return filtered


class CommonDataManagerInterface:
    async def load(self, eid):
        raise NotImplemented

    async def save(self, entity):
        raise NotImplemented

    async def patch(self, entity: object, *, only: Tuple = None, exclude: Tuple = None, prop_filter: Filter = None):
        raise NotImplemented

    async def find(self, properties: {}) -> []:
        raise NotImplemented

    async def find_one(self, eid=None, **kwargs):
        raise NotImplemented

    async def delete(self, eid):
        raise NotImplemented

    async def delete_many(self, properties: dict):
        raise NotImplemented


class StorageAdapter(CommonDataManagerInterface):
    """
    may contain driver specific logic on how to manipulate entities in storage
    """
    pass


class Repository(CommonDataManagerInterface):
    """
    may contain non-specific logic on how to manipulate entities in storage
    """
    def __init__(self, adapter: StorageAdapter):
        super().__init__()
        self.adapter = adapter

    def load(self, eid):
        return self.adapter.load(eid)

    def save(self, entity):
        return self.adapter.save(entity)

    def patch(self, entity: object, *, only: Tuple = None, exclude: Tuple = None, prop_filter: Filter = None):
        return self.adapter.patch(entity, only=only, exclude=exclude, prop_filter=prop_filter)

    def find(self, properties: {}) -> []:
        return self.adapter.find(properties)

    def find_one(self, eid=None, **kwargs):
        return self.adapter.find_one(eid=eid, **kwargs)

    def delete(self, eid):
        return self.adapter.delete(eid)

    def delete_many(self, properties: dict):
        return self.adapter.delete_many(properties)


class StorageException(Exception):
    pass


class DoesNotExist(StorageException):
    pass


class VersionMismatch(StorageException):
    pass
