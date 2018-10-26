import pytest

from container_manager.kubernetes import KubernetesProvider


@pytest.fixture(scope='module')
def provider() -> KubernetesProvider:
    kp = KubernetesProvider(
        user_space_namespace='gis',
        image_pull_secrets=['gitlab']
    )
    yield kp

    del kp


def test_kubernetes_find_ns(provider: KubernetesProvider):
    assert provider._usp_namespace_exists()
