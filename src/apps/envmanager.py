import os
from typing import Dict

from kubernetes.client import V1NFSVolumeSource

from common.healthcheck import HealthCheckAPI
from config import ROOT_LOG, SHARED_FS_MOUNT_PATH
from container_manager import Provider, ProviderKind
from container_manager.api import ContainerManagerRPCAPI
from container_manager.docker import DockerProvider
from container_manager.kubernetes import KubernetesProvider
from container_manager.manager import ContainerManager
from injector import configure_injector
from mco.rpc import RPCServerApplication

configure_injector()


class EnvironmentManagerApp(RPCServerApplication):
    @staticmethod
    def _config() -> Dict[ProviderKind, Provider]:
        data = {
            'docker-enabled': bool(os.getenv('PROVIDER_DOCKER_ENABLE', False)),
            'kubernetes-enabled': bool(os.getenv('PROVIDER_KUBERNETES_ENABLE', False)),
            'user-space-name': os.getenv('USER_SPACE_NAME', 'default'),
            'mount-prefix': os.getenv('MOUNT_PREFIX', '/opt/data'),
            'k8s': {
                'nfs-path': os.getenv('K8S_NFS_SHARE_PATH'),
                'nfs-server': os.getenv('K8S_NFS_SHARE_SERVER'),
                'pull-secrets': [str(s).strip() for s in str(os.getenv('K8S_IMAGE_PULL_SECRET_NAMES')).split(',')]
            }
        }
        provider_map = {}

        if data['docker-enabled'] and data['kubernetes-enable']:
            raise EnvironmentError('docker and kubernetes could not be both enabled')
        if data['kubernetes-enabled']:
            if not data['k8s']['nfs-path'] or not data['k8s']['nfs-server']:
                raise EnvironmentError('nfs shared fs info should be provided in order to mount models')
            if len(data['k8s']['pull-secrets']) == 1 and data['k8s']['pull-secrets'][0] == '':
                ROOT_LOG.info('no pull-secrets provided - only public images from hub.docker.io are available')
                data['k8s']['pull-secrets'] = []

        if data['docker-enabled']:
            provider_map[ProviderKind.Docker] = DockerProvider(
                user_space_network=os.getenv('USER_SPACE_NAME', 'buldozer_usp_net'),
                mount_prefix=SHARED_FS_MOUNT_PATH
            )
        elif data['kubernetes-enabled']:
            provider_map[ProviderKind.Docker] = KubernetesProvider(
                user_space_namespace=data['user-space-name'],
                nfs_share=V1NFSVolumeSource(
                    path=data['k8s']['nfs-path'],
                    server=data['k8s']['nfs-server'],
                    read_only=True
                ),
                image_pull_secrets=data['k8s']['pull-secrets']
            )

        return provider_map

    async def _setup(self):
        await super()._setup()

        self.controller = ContainerManagerRPCAPI(
            ContainerManager(self._config())
        )
        self.add_methods_from(self.controller)
        self.add_routes_from(
            HealthCheckAPI()
        )


if __name__ == '__main__':
    ROOT_LOG.info('starting [%s]', EnvironmentManagerApp.__name__)
    EnvironmentManagerApp().run()
