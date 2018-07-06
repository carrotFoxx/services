import asyncio
import functools
from typing import Callable, Coroutine


def run_in_executor(fn) -> Callable[[], Coroutine]:
    """
    simple sync wrapper - running an operation in asyncio threaded-pool
    :param fn:
    :return:
    """
    loop = asyncio.get_event_loop()

    def wrapper(*args, **kwargs):
        return loop.run_in_executor(None, functools.partial(fn, *args, **kwargs))

    return wrapper
