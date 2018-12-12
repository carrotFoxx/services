import abc
import asyncio
import json
import uuid
from asyncio import CancelledError
from datetime import datetime
from itertools import count, takewhile
from json import JSONEncoder
from typing import Any, AsyncIterator, Awaitable, Iterator

import bson
from marshmallow.utils import isoformat
from motor.core import AgnosticCollection

from mco.utils import convert_exceptions


class AbstractRecordGenerator(abc.ABC):
    @abc.abstractmethod
    def generate(self) -> Awaitable[str]:
        pass


class SampleRecordGenerator(AbstractRecordGenerator):
    def __init__(self, amount: int = -1, delay: float = 0.5) -> None:
        super().__init__()
        self._delay: float = abs(delay)
        self._break = False

        gen = count() if amount < 0 else range(amount)
        self._sequencer: Iterator = iter(takewhile(self._should_stop, gen))
        self._current = None

    @property
    def current(self) -> int:
        return self._current

    def kill(self):
        self._break = True

    def _should_stop(self, _: Any):
        return not self._break

    @convert_exceptions(exc=StopIteration, to=CancelledError)
    def generate(self) -> Awaitable[str]:
        self._current = next(self._sequencer)
        # sleeping for 0 seconds is optimized in asyncio, so we wont bother handling this
        return asyncio.sleep(self._delay, result=json.dumps(self._create_payload(self._current)))

    def _create_payload(self, seq_value: int):
        return {
            'seq': seq_value,
            'payload': ''
        }


class MongoRecordGenerator(AbstractRecordGenerator):
    def __init__(self, collection: AgnosticCollection, query: dict = None, delay: float = 0.0) -> None:
        super().__init__()
        self._delay = abs(delay)
        self._query = query
        self._collection = collection

        self._encoder = JSONEncoder(default=self._helper, ensure_ascii=False, separators=(',', ':'))
        self._sequencer: AsyncIterator = self._collection.find(self._query)
        self._current = None

    @convert_exceptions(exc=StopAsyncIteration, to=CancelledError)
    async def generate(self) -> str:
        self._current = await self._sequencer.__anext__()
        # sleeping for 0 seconds is optimized in asyncio, so we wont bother handling this
        return await asyncio.sleep(self._delay, result=self._create_payload(self._current))

    # specialized type converters for arbitrary BSON->JSON data transition
    _m = {
        bson.ObjectId: str,
        uuid.UUID: str,
        datetime: isoformat,
    }

    @classmethod
    def _helper(cls, o: Any):
        t = type(o)
        try:
            return cls._m[t](o)
        except KeyError:
            return str(o)

    def _create_payload(self, seq_value: dict) -> str:
        return self._encoder.encode(seq_value)
