import asyncio
import json
from asyncio import CancelledError
from itertools import count, takewhile
from typing import Any, Awaitable, Iterator

from mco.utils import convert_exceptions


class SampleRecordGenerator:
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
