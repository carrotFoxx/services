import importlib


class FQN:
    @staticmethod
    def _get_class_fqn(o: type) -> str:
        return '%s.%s' % (o.__module__, o.__qualname__)

    @staticmethod
    def _get_object_fqn(o: object) -> str:
        return '%s.%s' % (o.__class__.__module__, o.__class__.__qualname__)

    @staticmethod
    def _load_class_by_fqn(fqn: str) -> type:
        module_name, class_name = fqn.rsplit('.', 1)
        m = importlib.import_module(module_name)
        """:type : builtins.module"""
        try:
            cls = getattr(m, class_name)
            if isinstance(cls, type):
                return cls
            raise ImportError('fqn is not pointing to class def: %s' % fqn)
        except AttributeError:
            raise ImportError('no such class: %s' % fqn)

    @classmethod
    def get_fqn(cls, arg):
        if isinstance(arg, type):
            return cls._get_class_fqn(arg)
        else:
            return cls._get_object_fqn(arg)

    @classmethod
    def get_type(cls, fqn: str) -> type:
        return cls._load_class_by_fqn(fqn)


class BackOff:
    def __init__(self, attempts=5, increment=2, start_timeout=1):
        super().__init__()
        self._timeout = start_timeout
        self._timeout_configured = start_timeout
        self._attempts_configured = attempts
        self._attempts_left = attempts
        self._increment = increment

    class LimitReached(Exception):
        pass

    def next_timeout(self):
        next_value = self._timeout

        self._attempts_left -= 1
        self._timeout *= self._increment
        if self._attempts_left < 0:
            raise self.LimitReached(
                'back-off limit reached, %s attempts was performed, end timeout was %s'
                % (self._attempts_configured, self._timeout)
            )

        return next_value

    def reset(self):
        self._attempts_left = self._attempts_configured
        self._timeout = self._timeout_configured


class TimeBasedUUID:
    @staticmethod
    def from_timestamp(timestamp: float) -> str:
        """Generate a UUID from a host ID, sequence number, and the given time.
            If 'node' is not given, getnode() is used to obtain the hardware
            address.  If 'clock_seq' is given, it is used as the sequence number;
            otherwise a random 14-bit sequence number is chosen."""
        nanoseconds = int(timestamp * 1e9)
        # 0x01b21dd213814000 is the number of 100-ns intervals between the
        # UUID epoch 1582-10-15 00:00:00 and the Unix epoch 1970-01-01 00:00:00.
        # timestamp = int(nanoseconds / 100) + 0x01b21dd213814000
        from random import getrandbits
        clock_seq = getrandbits(24)
        from uuid import getnode
        node = getnode()

        str_repr = '%032x' % ((nanoseconds << 64) | (clock_seq << 48) | node)

        return '%s-%s-%s-%s-%s' % (str_repr[0:8], str_repr[8:12], str_repr[12:16], str_repr[16:20], str_repr[20:])
