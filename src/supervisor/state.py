import asyncio
import logging
from asyncio import CancelledError
from copy import copy
from typing import Callable

from common.consul import ConsulClient, consul_key
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
        return consul_key(CONSUL_SUBORDINATE_DIR, self.node_id, key)

    async def _adoption(self, version: int, data: dict):
        try:
            await self.adoption_cb(copy(data))
        except:
            logger.exception('failed to adopt version=%s', version)
        else:
            await self._signal_adoption(version)

    async def _pull_state(self):
        logger.debug('checking version, base=%s', self.version)
        remote_version = int(await self._consul_kv.get(self._consul_key(DESIRED_VERSION), raw=True, default=1))
        if self.version < remote_version:
            logger.info('refreshing, base=%s, remote=%s', self.version, remote_version)
            state = await self._consul_kv.get_all(self._consul_key(), raw=True)
            self.state.update(state)
        return remote_version

    async def _signal_adoption(self, version: int):
        if self.version > version:
            logger.warning('adoption is lagging behind: adopting=%s, desired=%s', version, self.version)
        self.version = version
        await self._consul_kv.put(self._consul_key(ADOPTED_VERSION), version)
        logger.info('adopted version=%s', version)

    async def task(self):
        logger.debug('launched state monitor bg task')
        while True:
            try:
                logger.debug('performing state synchronization...')
                remote_version = await self._pull_state()
                # todo: ensure linear processing
                if remote_version > self.version:
                    logger.info('start adoption from=%s to=%s', self.version, remote_version)
                    self._tm.add(str(remote_version), remote_version, self.state)
            except (CancelledError, GeneratorExit):
                logger.info('stopping state monitor bg task')
                raise
            except:
                logger.exception('resync state task resulted in error')
            await asyncio.sleep(RESYNC_INTERVAL)
