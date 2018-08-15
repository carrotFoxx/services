import asyncio
import logging
from typing import Awaitable

import docker
import docker.errors
from docker.models.containers import Container
from docker.models.networks import Network

from container_manager import InstanceNotFound, ProviderError
from container_manager.definition import Instance, InstanceDefinition
from mco.utils import convert_exceptions
from microcore.base.sync import run_in_executor

LABEL_PREFIX = 'com.buldozer.'
ORCHESTRATOR_ID = 'docker-provider'

log = logging.getLogger(__name__)

raise_provider_exception = convert_exceptions(exc=docker.errors.APIError, to=ProviderError)


class DockerProvider:
    def __init__(self, user_space_network: str = 'buldozer_usp_net', *, loop: asyncio.AbstractEventLoop = None) -> None:
        super().__init__()
        self.usp_network_name = user_space_network
        self._client = docker.DockerClient.from_env()
        self._loop = loop or asyncio.get_event_loop()

    @staticmethod
    def _normalize_labels(dct: dict):
        return {
            **{LABEL_PREFIX + key: str(value) for key, value in dct.items() if not key.startswith(LABEL_PREFIX)},
            **{key: str(value) for key, value in dct.items() if key.startswith(LABEL_PREFIX)},
            LABEL_PREFIX + 'project': 'buldozer',
            LABEL_PREFIX + 'provider': ORCHESTRATOR_ID
        }

    @raise_provider_exception
    def _usp_network_exists(self):
        nls = self._client.networks.list(names=[self.usp_network_name])
        return len(nls) > 0

    @raise_provider_exception
    def _create_usp_network(self) -> Network:
        return self._client.networks.create(
            name=self.usp_network_name,
            driver='bridge',
            labels=self._normalize_labels({
                'space': 'user_space',
            }),
            check_duplicate=True
        )

    @raise_provider_exception
    def _image_exists(self, definition: InstanceDefinition):
        return len(self._client.images.list(filters={'reference': definition.image})) == 1

    @raise_provider_exception
    def _launch_instance(self, definition: InstanceDefinition) -> Container:
        try:
            container = self._find_instance_container(definition)
            log.info('found existing container [%s] for [%s]', container.short_id, definition.uid)
        except InstanceNotFound:
            log.debug('no existing container found for [%s]', definition.uid)
            container = self._create_container(definition)

        if container.status != 'running':
            log.info('container [%s] is not running - starting...', container.short_id)
            container.start()
            log.info('container [%s] started', container.short_id)
        return container

    @raise_provider_exception
    def _create_container(self, definition) -> Container:
        if not self._image_exists(definition):
            log.info('pulling Instance image [%s]', definition.image)
            self._client.images.pull(*definition.image.split(':'))

        if not self._usp_network_exists():
            log.info('creating USP network')
            self._create_usp_network()

        log.info('creating container for %s', definition)
        return self._client.containers.create(
            image=definition.image,
            detach=True,
            network=self.usp_network_name,
            restart_policy={'Name': definition.restart_policy},
            volumes={vol: {'bind': mount, 'mode': 'ro'}
                     for vol, mount in definition.attachments.items()},
            environment=definition.environment,
            labels=self._normalize_labels(
                {**definition.labels,
                 'com.buldozer.instance_id': definition.uid}
            )
        )

    @raise_provider_exception
    def _find_instance_container(self, definition: InstanceDefinition) -> Container:
        containers_list = self._client.containers.list(
            all=True,
            filters={'label': 'com.buldozer.instance_id=%s' % definition.uid}
        )
        if len(containers_list) > 0:
            log.info('found instance for [%s] (cid:%s)', definition.uid, containers_list[0].short_id)
            return containers_list[0]
        raise InstanceNotFound

    @raise_provider_exception
    def _stop_instance(self, definition: InstanceDefinition):
        try:
            container = self._find_instance_container(definition)
            container.stop()
            container.wait()
            log.info('removed instance [%s] (cid:%s)', definition.uid, container.short_id)
            return True
        except InstanceNotFound:
            log.info('instance [%s] not found, assume it is already have been removed', definition.uid)
        return True

    @raise_provider_exception
    def _remove_instance(self, definition: InstanceDefinition):
        try:
            container = self._find_instance_container(definition)
            if container.status == 'running':
                container.stop()
                container.wait()
            container.remove()
        except InstanceNotFound:
            log.info('instance [%s] not found')
        return True

    @staticmethod
    def _c2i(container: Container) -> Instance:
        """
        converts docker.Container object to Instance object
        :param container:
        :return:
        """
        return Instance(
            uid=container.short_id,
            name=container.name,
            state=container.status
        )

    @run_in_executor
    def create_instance(self, definition: InstanceDefinition) -> Awaitable[Instance]:
        # noinspection PyTypeChecker
        return self._c2i(self._create_container(definition))

    @run_in_executor
    def launch_instance(self, definition: InstanceDefinition):
        return self._c2i(self._launch_instance(definition))

    @run_in_executor
    def stop_instance(self, definition: InstanceDefinition):
        return self._stop_instance(definition)

    @run_in_executor
    def remove_instance(self, definition: InstanceDefinition):
        return self._remove_instance(definition)
