import json
import logging
from typing import Awaitable

import attr

from common.consul import ConsulClient, consul_key
from common.entities import RouteConfig
from config import CONSUL_SUBORDINATE_DIR, CONSUL_TOPICS_CTL, CONSUL_TOPICS_DIR, SPV_STATE_KEY_ADOPTED_VERSION, \
    SPV_STATE_KEY_DESIRED_VERSION

log = logging.getLogger(__name__)


class Configurator:
    def __init__(self, consul: ConsulClient) -> None:
        super().__init__()
        self.consul = consul

    async def _get_adopted_version(self, uid: str) -> int:
        return int(await self.consul.kv.get(
            consul_key(CONSUL_SUBORDINATE_DIR, uid, SPV_STATE_KEY_ADOPTED_VERSION),
            raw=True,
            default=0
        ))

    async def _get_desired_version(self, uid: str):
        return int(await self.consul.kv.get(
            key=consul_key(CONSUL_SUBORDINATE_DIR, uid, SPV_STATE_KEY_DESIRED_VERSION),
            raw=True,
            default=0
        ))

    async def read(self, uid: str) -> RouteConfig:
        data: dict = await self.consul.kv.get_all(
            prefix=consul_key(CONSUL_SUBORDINATE_DIR, uid, ''),
            raw=True
        )
        return RouteConfig(wsp_uid=uid, **data)

    async def write(self, route: RouteConfig):
        """
        this is client part of supervisor.state.StateMonitor

        updates/creates node config in consul KV-store so supervisor could read it and configure itself
        """

        desired_version = await self._get_desired_version(route.wsp_uid)
        desired_version += 1  # increment to signal rerouting
        route.desired_version = desired_version
        # check and register topics
        await self._check_register_topic(route.incoming_stream)
        await self._check_register_topic(route.outgoing_stream)
        await self._increment_topic_config_version()
        # serialize and write-out config
        log.info('writing route config %s', route)
        props = attr.asdict(route, filter=lambda a, v: a.name != 'wsp_uid')
        await self.consul.kv.put_all(prefix=consul_key(CONSUL_SUBORDINATE_DIR, route.wsp_uid), data=props)

    def clear(self, uid: str) -> Awaitable[bool]:
        log.info('drop route config for [%s]', uid)
        return self.consul.kv.rem(consul_key(CONSUL_SUBORDINATE_DIR, uid), recurse=True)

    async def _topic_exist(self, topic: str) -> bool:
        return bool(await self.consul.kv.get(
            consul_key(CONSUL_TOPICS_DIR, topic),
            raw=True,
            default=False
        ))

    async def _topic_register(self, topic: str) -> bool:
        try:
            return await self.consul.kv.put(
                consul_key(CONSUL_TOPICS_DIR, topic),
                json.dumps({
                    "name": topic,
                    "partitions": 5,
                    "replicas": 1,
                    "properties": {}
                })
            )
        except self.consul.InteractionError:
            return False

    async def _check_register_topic(self, topic: str):
        if not await self._topic_exist(topic):
            log.info('topic=%s does not exists, registering' % topic)
            await self._topic_register(topic)

    async def _increment_topic_config_version(self) -> bool:
        key = consul_key(CONSUL_TOPICS_CTL, SPV_STATE_KEY_DESIRED_VERSION)
        desired_version = int(await self.consul.kv.get(key, raw=True, default=0))
        desired_version += 1
        return await self.consul.kv.put(key, value=desired_version)
