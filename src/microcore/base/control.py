import asyncio
import functools
import logging
from typing import Coroutine, Dict, Union

logger = logging.getLogger(__name__)


class AsyncIODelayedCallManager:
    def __init__(self, op_callback: callable, delay=0, loop: asyncio.AbstractEventLoop = None) -> None:
        super().__init__()
        self.delay = delay
        self._loop = loop or asyncio.get_event_loop()
        self._handles: Dict[str, asyncio.Handle] = {}
        self._callable: callable = op_callback

    def add(self, hid: str, *args, **kwargs):
        callback = self._callable if not kwargs else functools.partial(self._callable, **kwargs)
        return self._attach(hid, callback, *args)

    def remove(self, hid: str):
        return self._detach(hid)

    def _attach(self, hid: str, callback: callable, *args):
        self._detach(hid)
        handle: asyncio.Handle = self._loop.call_later(self.delay, self._handler, hid, callback, *args)
        self._handles[hid] = handle
        logger.debug('callback-manager: add handle for %s(%s) args: %s', repr(self._callable), hid, args)

    def _detach(self, hid: str):
        handle = self._handles.pop(hid, None)
        if handle is not None:
            handle.cancel()
            logger.debug('callback-manager: remove handle for %s(%s)', repr(self._callable), hid)
            return True
        return False

    def _handler(self, hid: str, fn: callable, *args):
        self._detach(hid)
        return fn(hid, *args)


class _BaseTaskManager:
    def __init__(self, loop: asyncio.AbstractEventLoop = None) -> None:
        super().__init__()
        self._loop = loop or asyncio.get_event_loop()
        self._handles: Dict[str, asyncio.Task] = {}

    def __iter__(self):
        return iter(self._handles.values())

    def _attach(self, hid: str, coro: Coroutine):
        task: asyncio.Task = self._loop.create_task(coro)
        task.add_done_callback(lambda fut: self._detach(hid))
        self._handles[hid] = task
        logger.debug('task-manager: add handle %s', hid)

    def _detach(self, hid: str):
        handle = self._handles.pop(hid, None)
        if handle is not None:
            handle.cancel()
            logger.debug('task-manager: remove handle [%s]', hid)
            return True
        return False


class AsyncIOBackgroundManager(_BaseTaskManager):
    def add(self, hid: str, coro: Coroutine):
        if hid not in self._handles:
            self._attach(hid, coro)
        else:
            logger.debug('task-manager: handle [%s] already exists', hid)
        return self._handles[hid]

    def remove(self, hid: str):
        return self._detach(hid)

    def get(self, hid: str) -> Union[asyncio.Task, None]:
        return self._handles.get(hid, None)


class AsyncIOTaskManager(_BaseTaskManager):
    def __init__(self, op_callback: callable, loop: asyncio.AbstractEventLoop = None) -> None:
        super().__init__(loop=loop)
        self._callable: callable = op_callback

    def add(self, hid: str, *args, **kwargs):
        if hid not in self._handles:
            self._attach(hid, self._callable(*args, **kwargs))
            logger.debug('task-manager: add handle for %s(%s) args: %s kwargs: %s',
                         repr(self._callable), hid, args, kwargs)
        else:
            logger.debug('task-manager: handle already exists for %s(%s)', repr(self._callable), hid)
        return self._handles[hid]

    def remove(self, hid: str):
        return self._detach(hid)

    def get(self, hid) -> Union[asyncio.Task, None]:
        return self._handles.get(hid, None)
