import abc


class Identifiable(abc.ABC):
    @abc.abstractmethod
    def get_uid(self):
        pass

    @abc.abstractmethod
    def set_uid(self, value: str):
        pass


class Owned(abc.ABC):
    @abc.abstractmethod
    def get_owner(self):
        pass

    @abc.abstractmethod
    def set_owner(self, value: str):
        pass


class Preserver(abc.ABC):
    @abc.abstractmethod
    def preserve_from(self, other):
        pass
