import asyncio
from typing import Awaitable

import kubernetes as k8s
from kubernetes.client import V1Container, V1Deployment, V1DeploymentCondition, V1DeploymentList, V1DeploymentSpec, \
    V1DeploymentStatus, V1DeploymentStrategy, V1EnvVar, V1LabelSelector, V1LocalObjectReference, V1Namespace, \
    V1NamespaceList, V1ObjectMeta, V1PersistentVolumeClaimVolumeSource, V1PodSpec, V1PodTemplateSpec, V1Volume, \
    V1VolumeMount
from kubernetes.client.rest import ApiException
from kubernetes.config import ConfigException

from container_manager import Instance, InstanceDefinition, InstanceNotFound, Provider, ProviderError
from mco.utils import convert_exceptions
from microcore.base.sync import run_in_executor

raise_provider_exception = convert_exceptions(exc=ApiException, to=ProviderError)


class KubernetesProvider(Provider):
    ORCHESTRATOR_ID = 'kubernetes'

    def __init__(self, user_space_namespace: str = 'buldozer_usp_net',
                 image_pull_secrets=None,
                 *,
                 loop: asyncio.AbstractEventLoop = None) -> None:
        super().__init__()
        self._loop = loop or asyncio.get_event_loop()

        self.image_pull_secrets: list = image_pull_secrets or []
        self.usp_namespace_name: str = user_space_namespace
        try:
            k8s.config.incluster_config.load_incluster_config()
        except ConfigException:
            k8s.config.load_kube_config()

    @staticmethod
    def _d2i(deployment: V1Deployment) -> Instance:
        """
        convert deployment to instance
        :return:
        """
        meta: k8s.client.V1ObjectMeta = deployment.metadata
        status: V1DeploymentStatus = deployment.status

        available_cond: V1DeploymentCondition = None
        for cond in status.conditions:  # type: V1DeploymentCondition
            if cond.type == "Available":
                available_cond = cond
                break

        return Instance(
            uid=meta.uid,
            name=f'{meta.namespace}/{meta.name}',
            state="running" if available_cond.status == "True" else "progressing"
        )

    @raise_provider_exception
    def _usp_namespace_exists(self):
        namespaces: V1NamespaceList = k8s.client.CoreV1Api().list_namespace()
        for ns in namespaces.items:  # type: V1Namespace
            if ns.metadata.name == self.usp_namespace_name:
                return True
        return False

    @raise_provider_exception
    def _create_usp_namespace(self) -> V1Namespace:
        return k8s.client.CoreV1Api().create_namespace(
            body=V1Namespace(
                api_version='v1',
                kind='Namespace',
                metadata=V1ObjectMeta(
                    name=self.usp_namespace_name,
                    labels=self._normalize_labels({
                        'space': 'user_space'
                    })
                )
            )
        )

    @raise_provider_exception
    def _find_deployment(self, definition: InstanceDefinition):
        deployments: V1DeploymentList = k8s.client.AppsV1Api().list_namespaced_deployment(
            namespace=self.usp_namespace_name,
            field_selector=None,  # todo: fix to appropriate selector
            label_selector=None
        )
        for dep in deployments.items:  # type: V1Deployment
            if dep.metadata.name == 'wsp_%s' % definition.uid:
                return dep
        raise InstanceNotFound

    @raise_provider_exception
    def _create_deployment(self, definition: InstanceDefinition, replicas=0) -> V1Deployment:
        return k8s.client.AppsV1Api().create_namespaced_deployment(
            namespace=self.usp_namespace_name,
            body=self._create_deployment_definition(definition, replicas=replicas)
        )

    def _create_deployment_definition(self, definition: InstanceDefinition, replicas=0) -> V1Deployment:
        return V1Deployment(
            api_version="apps/v1",
            kind="Deployment",
            metadata=V1ObjectMeta(
                namespace=self.usp_namespace_name,
                name='wsp_%s' % definition.uid,
                labels=self._normalize_labels(
                    {**definition.labels,
                     'instance_id': definition.uid}
                )
            ),
            spec=V1DeploymentSpec(
                min_ready_seconds=30,
                progress_deadline_seconds=300,
                replicas=replicas,
                selector=V1LabelSelector(
                    match_labels=self._normalize_labels(
                        {'instance_id': definition.uid}
                    )
                ),
                strategy=V1DeploymentStrategy(
                    type="Recreate"
                ),
                template=V1PodTemplateSpec(
                    metadata=V1ObjectMeta(
                        labels=self._normalize_labels({
                            **definition.labels,
                            'instance_id': definition.uid
                        })
                    ),
                    spec=V1PodSpec(
                        automount_service_account_token=False,
                        image_pull_secrets=[V1LocalObjectReference(name='gitlab')],
                        containers=[V1Container(
                            name='supervised_process',
                            image_pull_policy='Always',
                            image=definition.image,
                            termination_message_policy='FallbackToLogsOnError',
                            env=[V1EnvVar(name=env_key, value=env_val)
                                 for env_key, env_val in definition.environment.items()],
                            volume_mounts=[V1VolumeMount(
                                name='shared_fs',
                                mount_path=mount,
                                sub_path=sub_path,
                                read_only=True
                            ) for mount, sub_path in definition.attachments.items()],
                        )],
                        termination_grace_period_seconds=120,
                        volumes=[
                            # should mount shared model storage here
                            # todo: check and test this
                            V1Volume(
                                name='shared_fs',
                                persistent_volume_claim=V1PersistentVolumeClaimVolumeSource(
                                    claim_name='buldozer_shared_fs',
                                    read_only=True
                                )
                            )
                        ]
                    )
                )
            )
        )

    @run_in_executor
    def create_instance(self, definition: InstanceDefinition) -> Awaitable[Instance]:
        # noinspection PyTypeChecker
        return self._d2i(self._create_deployment(definition, replicas=0))

    def launch_instance(self, definition: InstanceDefinition) -> Awaitable[Instance]:
        pass

    def stop_instance(self, definition: InstanceDefinition) -> Awaitable[bool]:
        pass

    def remove_instance(self, definition: InstanceDefinition) -> Awaitable[bool]:
        pass
