import os
from typing import Dict

from kubernetes.client import V1NFSVolumeSource

from common.application_mixin import CommonAppMixin
from config import ROOT_LOG, SHARED_FS_MOUNT_PATH
from container_manager import ProviderKind, VmProviderKind
from container_manager.api import ContainerManagerRPCAPI
from container_manager.docker import DockerProvider
from container_manager.kubernetes import KubernetesProvider
from container_manager.manager import ContainerManager
from container_manager.provider import Provider
from container_manager.vm import VmProvider
from injector import configure_injector
from mco.rpc import RPCServerApplication

configure_injector()


class EnvironmentManagerApp(RPCServerApplication, CommonAppMixin):
    @staticmethod
    def _config() -> Dict[ProviderKind, Provider]:
        data = {
            'docker-enabled': bool(os.getenv('PROVIDER_DOCKER_ENABLE', False)),
            'kubernetes-enabled': bool(os.getenv('PROVIDER_KUBERNETES_ENABLE', False)),
            'vm-enabled': bool(os.getenv('PROVIDER_VM_ENABLE', False)),
            'user-space-name': os.getenv('USER_SPACE_NAME', 'default'),
            'k8s': {
                'nfs-path': os.getenv('K8S_NFS_SHARE_PATH'),
                'nfs-server': os.getenv('K8S_NFS_SHARE_SERVER'),
                'pull-secrets': [str(s).strip() for s in str(os.getenv('K8S_IMAGE_PULL_SECRET_NAMES', '')).split(',')]
            }
        }
        provider_map = {}

        if data['docker-enabled'] and data['kubernetes-enabled']:
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
        if data['vm-enabled']:
            provider_map[ProviderKind.VirtualMachine] = VmProvider(
                vm_provider=os.getenv('PROVIDER_VM_KIND', VmProviderKind.Openstack),
                vm_provider_cred={
                    'auth_url': os.getenv('OPENSTACK_AUTH_URL', 'http://192.168.116.195:5000/v3/'),
                    'username': os.getenv('OPENSTACK_USERNAME', 'gis_service_user'),
                    'password': os.getenv('OPENSTACK_PASSWORD', 'a01mr73ncyq'),
                    'project_name': os.getenv('OPENSTACK_PROJECT_NAME', 'gis'),
                    'user_domain_id': os.getenv('OPENSTACK_USER_DOMAIN_ID', 'default'),
                    'project_domain_id': os.getenv('OPENSTACK_PROJECT_DOMAIN_ID', 'default'),
                },
                vm_instance_definitions={
                    'security_groups': os.getenv('OPENSTACK_SECURITY_GROUPS', 'default, gis_sg'),
                    'availability_zone': os.getenv('OPENSTACK_AVAILABILITY_ZONE', 'nova'),
                    'key_name': os.getenv('OPENSTACK_KEY_NAME', 'devops'),
                    'networks': os.getenv('OPENSTACK_NETWORKS', 'bc9d2afc-c565-4f86-bd1d-3aa156963065'),
                    'bdz_kafka_dsn': os.getenv('BDZ_KAFKA_DSN', None),
                    'bdz_consul_dsn': os.getenv('BDZ_CONSUL_DSN', None),
                }
            )
        ROOT_LOG.info("acquired configuration:\n%s\n%s", provider_map, data)
        return provider_map

    async def _setup(self):
        await super()._setup()

        self.controller = ContainerManagerRPCAPI(
            ContainerManager(self._config())
        )
        self.add_methods_from(self.controller)


if __name__ == '__main__':
    ROOT_LOG.info('starting [%s]', EnvironmentManagerApp.__name__)
    EnvironmentManagerApp().run()
