import logging
import pprint

import pytest
from docker.models.containers import Container

from container_manager.definitions import InstanceDefinition
from container_manager.docker import DockerProvider

log = logging.getLogger()


@pytest.fixture(scope='module')
def docker_client() -> DockerProvider:
    dc: DockerProvider = DockerProvider(

    )
    yield dc
    del dc


@pytest.mark.asyncio
async def test_create_container(docker_client: DockerProvider):
    docker_client: DockerProvider
    log.info('creating container')
    definition = InstanceDefinition(uid='test_instance', image='busybox:latest')
    container: Container = await docker_client.launch_instance(definition)
    log.info('container created:\n%s', pprint.pformat(container))
    await docker_client.stop_instance(definition)
