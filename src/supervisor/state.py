import asyncio
import logging
from copy import copy
from typing import Callable

from common.consul import ConsulClient
from config import CONSUL_SUBORDINATE_DIR
from microcore.base.control import AsyncIOTaskManager

RESYNC_INTERVAL = 60

DESIRED_VERSION = 'desired_version'
ADOPTED_VERSION = 'adopted_version'

logger = logging.getLogger(__name__)


class StateMonitor:
    def __init__(self, node_id: str, consul: ConsulClient,
                 adoption_cb: Callable[[dict], None] = None,
                 loop: asyncio.AbstractEventLoop = None) -> None:
        super().__init__()
        self.loop = loop or asyncio.get_event_loop()
        self.node_id = node_id

        self.consul = consul
        self._consul_kv = consul.kv()

        self.state = {}
        self.version = 0

        self.adoption_cb = adoption_cb
        self._tm = AsyncIOTaskManager(op_callback=self._adoption)

    def _consul_key(self, key: str = '') -> str:
        return CONSUL_SUBORDINATE_DIR + self.node_id + '/' + key.lstrip('/')

    async def _adoption(self, version: int, data: dict):
        try:
            await self.adoption_cb(copy(data))
        except:
            logger.exception('failed to adopt version=%s', version)
        else:
            await self._signal_adoption(version)

    async def _pull_state(self):
        logger.debug('checking version, base=%s', self.version)
        if self.version > 0:
            remote_version = int(await self._consul_kv.get(self._consul_key(DESIRED_VERSION), raw=True))
        else:
            remote_version = -1

        if self.version >= remote_version:
            logger.debug('skip refresh, base=%s', self.version)
            return
        logger.info('refreshing, base=%s, remote=%s', self.version, remote_version)
        state = await self._consul_kv.get_all(self._consul_key())
        self.state.update(state)

    async def _signal_adoption(self, version: int):
        if self.version > version:
            logger.warning('adoption is lagging behind: adopting=%s, desired=%s', version, self.version)
        await self._consul_kv.put(self._consul_key(ADOPTED_VERSION), version)

    async def task(self):
        logger.debug('launched state monitor bg task')
        while True:
            logger.debug('performing state synchronization...')
            current_version = self.version
            await self._pull_state()
            # todo: ensure linear processing
            if current_version < self.version:
                logger.info('start adoption from=%s to=%s', current_version, self.version)
                self._tm.add(str(self.version), self.state)
            await asyncio.sleep(RESYNC_INTERVAL)
