import asyncio
import logging
from pprint import pformat

import inject

from microcore.base.control import AsyncIOBackgroundManager
from supervisor.state import StateMonitor

logger = logging.getLogger(__name__)


class Supervisor:
    consul = inject.attr('consul')

    def __init__(self,
                 state_monitor: StateMonitor,
                 loop: asyncio.AbstractEventLoop = None) -> None:
        super().__init__()
        self.state_monitor = state_monitor
        self._loop = loop or asyncio.get_event_loop()
        self._tm = AsyncIOBackgroundManager(loop=self._loop)

    async def _adopt(self, data: dict):
        logger.info('adopted config...\b%s', pformat(data))

    async def start(self):
        self.state_monitor.adoption_cb = self._adopt
        self._tm.add('state_monitor', self.state_monitor.task())

    async def stop(self):
        self._tm.remove('state_monitor')

    def _kafka_consumer(self):
        pass

    def _kafka_producer(self):
        pass

    def _engine_controller(self):
        pass
