import logging

import pytest
from kubernetes.client import V1NFSVolumeSource

from container_manager.definitions import InstanceDefinition
from container_manager.kubernetes import KubernetesProvider


# BEWARE! THIS WILL USE FIRST AVAILABLE SELECTED KUBECTL CONTEXT FOUND ON YOUR MACHINE


@pytest.fixture(scope='module')
def provider() -> KubernetesProvider:
    kp = KubernetesProvider(
        user_space_namespace='gis',
        image_pull_secrets=['gitlab'],
        nfs_share=V1NFSVolumeSource(
            read_only=True,
            path="/mnt/storage",
            server="10.0.0.11",
        )
    )
    yield kp

    del kp


def test_kubernetes_find_ns(provider: KubernetesProvider):
    assert provider._usp_namespace_exists()


TEST_DEF_ID = 'test-id'


@pytest.fixture
def definition() -> InstanceDefinition:
    return InstanceDefinition(
        uid=TEST_DEF_ID,
        image='ubuntu:16.04',
        attachments={
            "/var/model": "opt/data/123",
        },
        environment={

        },
        labels={
            'pytest.local/test': TEST_DEF_ID
        }
    )


@pytest.mark.asyncio
async def test_create_instance(provider: KubernetesProvider, definition: InstanceDefinition):
    instance = await provider.create_instance(definition)
    logging.info(instance)


@pytest.mark.asyncio
async def test_launch_instance(provider: KubernetesProvider, definition: InstanceDefinition):
    instance = await provider.launch_instance(definition)
    logging.info(instance)


@pytest.mark.asyncio
async def test_stop_instance(provider: KubernetesProvider, definition: InstanceDefinition):
    assert await provider.stop_instance(definition)


@pytest.mark.asyncio
async def test_remove_instance(provider: KubernetesProvider, definition: InstanceDefinition):
    assert await provider.remove_instance(definition)
