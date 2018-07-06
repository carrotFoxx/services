"""
Sequentialization Toolkit.

Aim of this Toolkit is to provide means to ensure sequential asyncio task execution
within separate asyncio-threads when tasks are received in unblocking fashion and have
floating completion times.

In other words this toolkit ensures what tasks received from different threads
are coming to single thread and completed one after another without going in "parallel"
thus possibly maintaining global state or order of execution without the need of
resolving back to the sequential "blocking" read from task sources.

Common example:

reading from RMQ channel and immediately casting task processing to another green-thread
(allowing reader thread to receive next event without waiting for previous to complete)
on a multiplexed event stream where identified parts of a stream could be executed "in parallel",
if implemented without such concern it could lead to competing execution and
incorrect execution order (race-conditions), which is crucial.
"""

import asyncio
import datetime
import logging
from asyncio import CancelledError, Queue
from typing import Any, Awaitable, Callable, Dict, List

from microcore.base.utils import FQN

logger = logging.getLogger(__name__)


class SequentialThread:
    def __init__(self, uid: str, handler: Callable[[Any], Awaitable], loop=None) -> None:
        super().__init__()
        self.uid = uid
        self._handler = handler
        self._loop: asyncio.AbstractEventLoop = loop or asyncio.get_event_loop()
        self._task: asyncio.Task = None
        self._stop = False
        self._q = Queue(loop=self._loop)
        self._last_run = datetime.datetime.now()

        self.start()

    @property
    def last_run(self) -> datetime.datetime:
        return self._last_run

    @property
    def is_running(self):
        if not self._task:
            return False
        return not self._task.done()

    def put(self, item: Any):
        """
        coroutine
        :param item: to add for thread queue
        """
        return self._q.put(item)

    def put_nowait(self, item: Any):
        return self._q.put_nowait(item)

    class ThreadAlreadyRunning(Exception):
        pass

    def start(self):
        if self._task:
            raise self.ThreadAlreadyRunning()

        self._stop = False
        self._task = self._loop.create_task(self._run())
        return self._task

    def stop(self):
        self._stop = True

    def kill(self):
        self._stop = True
        self._task.cancel()

    async def _run(self):
        logger.info('launching %s', self)
        while not self._stop:
            try:
                item = await self._q.get()
                self._last_run = datetime.datetime.now()
                logger.debug('receive task on %s', self)
                await self._handler(item)
                self._q.task_done()
                logger.debug('handled task on %s', self)
            except (CancelledError, GeneratorExit):
                logger.info('stopping thread %s', self)
                return
            except:
                logger.exception('uncaught error on thread %s', self)
        logger.info('grace-stop thread %s', self)

    def __repr__(self) -> str:
        return '<%s uid=%s>' % (FQN.get_fqn(self), self.uid)

    def __str__(self) -> str:
        return self.__repr__()


class SequentialExecutionManager:
    def __init__(self, *, handler: Callable[[Any], Awaitable] = None,
                 reaper_interval: int = 30, reap_after: datetime.timedelta = None,
                 loop=None) -> None:
        """
        :param reaper_interval: interval in minutes, how often to try to reap threads
        :param reap_after: timedelta to reap threads last run older then this value (2x to force kill)
        :param handler: handler to automatically instantiate new threads with, if passed
        """
        super().__init__()
        self._reap_after = reap_after or datetime.timedelta(minutes=10)
        self._reaper_interval = reaper_interval
        self.handler = handler
        self._loop = loop or asyncio.get_event_loop()
        self._threads: Dict[str, SequentialThread] = {}
        self._reaper_thread: asyncio.Task = self._loop.create_task(self._thread_reaper())

    class NoThreadExists(Exception):
        pass

    async def handle(self, thread_id: str, item: Any):
        if thread_id not in self._threads and not self.handler:
            raise self.NoThreadExists(thread_id)
        if thread_id not in self._threads:
            self.add_thread(SequentialThread(thread_id, self.handler, loop=self._loop))

        return await self._threads[thread_id].put(item)

    def add_thread(self, thread: SequentialThread):
        self._threads[thread.uid] = thread

    async def stop(self):
        self._reaper_thread.cancel()
        for thread in self._threads.values():
            thread.stop()
        await asyncio.sleep(2)
        [thread.kill() for thread in self._threads.values() if thread.is_running]
        self._threads = {}

    async def _thread_reaper(self):
        logger.info('launching thread reaper')
        while True:
            reaped = []
            try:
                now = datetime.datetime.now()

                reaped: List[SequentialThread] = [
                    thread for thread in self._threads.values()
                    if now - thread.last_run > self._reap_after
                ]

                for thread in reaped:
                    thread.stop()

                await asyncio.sleep(self._reaper_interval)
            except (CancelledError, GeneratorExit):
                logger.info('stopping thread reaper')
                return
            finally:
                for thread in reaped:
                    if thread.is_running:
                        thread.kill()
                    del self._threads[thread.uid]
