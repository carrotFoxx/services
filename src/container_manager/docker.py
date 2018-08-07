import asyncio
import logging
from typing import Type

import docker
import docker.errors
from docker.models.containers import Container
from docker.models.networks import Network

from container_manager import InstanceNotFound, ProviderError
from container_manager.definition import InstanceDefinition
from microcore.base.sync import run_in_executor

ORCHESTRATOR_ID = 'docker-provider'

log = logging.getLogger(__name__)


def convert_exception(fn=None, *, to: Type[Exception] = None):
    exception_class = to or ProviderError

    def decorator(fn):
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except docker.errors.APIError as e:
                raise exception_class(str(e)) from e

        return wrapper

    return decorator(fn) if fn else decorator


class DockerProvider:
    def __init__(self, user_space_network: str = 'buldozer_usp_net', *, loop: asyncio.AbstractEventLoop = None) -> None:
        super().__init__()
        self.usp_network_name = user_space_network
        self._client = docker.DockerClient.from_env()
        self._loop = loop or asyncio.get_event_loop()

    @convert_exception
    def _usp_network_exists(self):
        nls = self._client.networks.list(names=[self.usp_network_name])
        return len(nls) > 0

    @convert_exception
    def _create_usp_network(self) -> Network:
        return self._client.networks.create(
            name=self.usp_network_name,
            driver='bridge',
            labels={
                'buldozer_network_purpose': 'user_space',
                'project': 'buldozer'
            },
            check_duplicate=True
        )

    @convert_exception
    def _image_exists(self, definition: InstanceDefinition):
        return len(self._client.images.list(filters={'reference': definition.image})) == 1

    @convert_exception
    def _launch_instance(self, definition: InstanceDefinition) -> Container:
        if not self._image_exists(definition):
            log.info('pulling Instance image [%s]', definition.image)
            self._client.images.pull(*definition.image.split(':'))

        if not self._usp_network_exists():
            log.info('creating USP network')
            self._create_usp_network()

        try:
            container = self._find_instance_container(definition)
            log.info('found existing container')
            return container
        except ProviderError:
            pass

        log.info('creating container for %s', definition)
        return self._client.containers.run(
            image=definition.image,
            detach=True,
            network=self.usp_network_name,
            restart_policy={'Name': definition.restart_policy},
            volumes={vol: {'bind': mount, 'mode': 'ro'} for vol, mount in definition.attachments.items()},
            labels={**definition.labels,
                    'com.buldozer.instance_id': definition.uid,
                    'com.buldozer.orchestrator': ORCHESTRATOR_ID}
        )

    @convert_exception
    def _find_instance_container(self, definition: InstanceDefinition) -> Container:
        containers_list = self._client.containers.list(all=True, filters={
            'label': 'com.buldozer.instance_id=%s' % definition.uid})
        if len(containers_list) > 0:
            log.info('found instance for [%s] (cid:%s)', definition.uid, containers_list[0].short_id)
            return containers_list[0]
        raise InstanceNotFound

    @convert_exception
    def _stop_instance(self, definition: InstanceDefinition):
        try:
            container = self._find_instance_container(definition)
            container.stop()
            container.wait()
            container.remove()
            log.info('removed instance [%s] (cid:%s)', definition.uid, container.short_id)
            return True
        except ProviderError:
            log.info('instance [%s] not found, assume it is already have been removed', definition.uid)
            pass
        return True

    @run_in_executor
    def launch_instance(self, definition: InstanceDefinition) -> Container:
        return self._launch_instance(definition)

    @run_in_executor
    def stop_instance(self, definition: InstanceDefinition):
        return self._stop_instance(definition)
