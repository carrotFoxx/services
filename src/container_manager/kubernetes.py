import asyncio
import logging
from typing import Awaitable

import kubernetes as k8s
from kubernetes.client import V1Container, V1DeleteOptions, V1Deployment, V1DeploymentCondition, V1DeploymentList, \
    V1DeploymentSpec, V1DeploymentStatus, V1DeploymentStrategy, V1EnvVar, V1LabelSelector, V1LocalObjectReference, \
    V1NFSVolumeSource, V1Namespace, V1NamespaceList, V1ObjectMeta, V1PodSpec, V1PodTemplateSpec, V1Scale, V1ScaleSpec, \
    V1Status, V1Volume, V1VolumeMount
from kubernetes.client.rest import ApiException
from kubernetes.config import ConfigException

from container_manager import Instance, InstanceDefinition, InstanceNotFound, Provider, ProviderError
from container_manager.attachment import FileAttachment
from mco.utils import convert_exceptions
from microcore.base.sync import run_in_executor

WSP_NAME_TPL = '%s.wsp.bdz'
VOL_NAME_TPL = '%s-vol-bdz'

log = logging.getLogger(__name__)
raise_provider_exception = convert_exceptions(exc=ApiException, to=ProviderError)


# BEWARE! THIS TEST WILL USE FIRST AVAILABLE DEFAULT KUBECTL CONTEXT FOUND ON YOUR MACHINE

class KubernetesProvider(Provider):
    ORCHESTRATOR_ID = 'kubernetes'

    def __init__(self,
                 user_space_namespace: str,
                 nfs_share: V1NFSVolumeSource,
                 image_pull_secrets=None,
                 *, loop: asyncio.AbstractEventLoop = None) -> None:
        super().__init__()
        self._loop = loop or asyncio.get_event_loop()

        self.image_pull_secrets: list = image_pull_secrets or []
        self.usp_namespace_name: str = user_space_namespace
        self.nfs_share = nfs_share
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

        available_cond: str = "unknown"
        if status.conditions is not None:
            for cond in status.conditions:  # type: V1DeploymentCondition
                if cond.type == "Available":
                    available_cond = "running" if cond.status == "True" else "pending"
                    break
        else:
            available_cond = "pending"

        return Instance(
            uid=meta.uid,
            name=f'{meta.namespace}/{meta.name}',
            state=available_cond
        )

    @raise_provider_exception
    def _usp_namespace_exists(self):
        namespaces: V1NamespaceList = k8s.client.CoreV1Api().list_namespace(
            field_selector='metadata.name=%s' % self.usp_namespace_name
        )
        if len(namespaces.items) < 1:
            return False
        for ns in namespaces.items:  # type: V1Namespace
            if ns.metadata.name == self.usp_namespace_name:
                return True
        return False

    @raise_provider_exception
    def _find_deployment(self, definition: InstanceDefinition):
        deployments: V1DeploymentList = k8s.client.AppsV1Api().list_namespaced_deployment(
            namespace=self.usp_namespace_name,
            label_selector=','.join(['='.join([k, v]) for k, v in self._normalize_labels(definition.labels).items()])
        )
        for dep in deployments.items:  # type: V1Deployment
            if dep.metadata.name == WSP_NAME_TPL % definition.uid:
                return dep
        raise InstanceNotFound

    @raise_provider_exception
    def _create_deployment(self, definition: InstanceDefinition, replicas=0) -> V1Deployment:
        return k8s.client.AppsV1Api().create_namespaced_deployment(
            namespace=self.usp_namespace_name,
            body=self._create_deployment_definition(definition, replicas=replicas)
        )

    def _create_deployment_definition(self, definition: InstanceDefinition, replicas=0) -> V1Deployment:
        image = self._extract_image(definition.image)
        return V1Deployment(
            api_version="apps/v1",
            kind="Deployment",
            metadata=V1ObjectMeta(
                namespace=self.usp_namespace_name,
                name=WSP_NAME_TPL % definition.uid,
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
                        image_pull_secrets=[V1LocalObjectReference(name=secret_name)
                                            for secret_name in self.image_pull_secrets],
                        termination_grace_period_seconds=120,
                        containers=[V1Container(
                            name='supervised-process',
                            image_pull_policy='Always',
                            image=image,
                            termination_message_policy='FallbackToLogsOnError',
                            env=[V1EnvVar(name=env_key, value=env_val)
                                 for env_key, env_val in definition.environment.items()],
                            volume_mounts=[V1VolumeMount(
                                name=VOL_NAME_TPL % definition.uid,
                                mount_path=mount,
                                sub_path=FileAttachment(sub_path, '/').path,
                                read_only=True
                            ) for mount, sub_path in definition.attachments.items()],
                        )],
                        volumes=[V1Volume(
                            name=VOL_NAME_TPL % definition.uid,
                            nfs=self.nfs_share
                        )]
                    )
                )
            )
        )

    @raise_provider_exception
    def _scale_deployment(self, deployment: V1Deployment, replicas: int) -> V1Scale:
        return k8s.client.AppsV1Api().replace_namespaced_deployment_scale(
            name=deployment.metadata.name,
            namespace=deployment.metadata.namespace,
            body=V1Scale(
                api_version="autoscaling/v1",
                kind="Scale",
                metadata=V1ObjectMeta(
                    namespace=deployment.metadata.namespace,
                    name=deployment.metadata.name
                ),
                spec=V1ScaleSpec(
                    replicas=replicas
                )
            )
        )

    @raise_provider_exception
    def _delete_deployment(self, deployment: V1Deployment) -> bool:
        status: V1Status = k8s.client.AppsV1Api().delete_namespaced_deployment(
            name=deployment.metadata.name,
            namespace=deployment.metadata.namespace,
            body=V1DeleteOptions(
                api_version='v1',
                kind='DeleteOptions',
                propagation_policy="Background"
            )
        )
        return status.status == "Success"

    @raise_provider_exception
    def _launch_instance(self, definition: InstanceDefinition) -> V1Deployment:
        try:
            dep = self._find_deployment(definition)
            log.info("found deployment [%s], belonging to def[%s]", dep.metadata.uid, definition.uid)
            if dep.spec.replicas < 1:
                log.info("scaling up deployment [%s] to launch def[%s]", dep.metadata.uid, definition.uid)
                self._scale_deployment(dep, replicas=1)
            return dep
        except InstanceNotFound:
            log.info("no deployment found for def[%s]", definition.uid)
            dep = self._create_deployment(definition, replicas=1)
            log.info("created deployment [%s] from def[%s] with scale=%s",
                     dep.metadata.uid, definition.uid, dep.spec.replicas)
            return dep

    @raise_provider_exception
    def _stop_instance(self, definition: InstanceDefinition) -> bool:
        try:
            dep = self._find_deployment(definition)
            log.info("found deployment [%s], belonging to def[%s]", dep.metadata.uid, definition.uid)
            self._scale_deployment(dep, replicas=0)
            log.info("scaled down deployment [%s]", dep.metadata.uid)
        except InstanceNotFound:
            log.info('deployment belonging to def[%s] not found, assume it is already have been removed',
                     definition.uid)
            return True

        return True

    @raise_provider_exception
    def _remove_instance(self, definition: InstanceDefinition) -> bool:
        try:
            dep = self._find_deployment(definition)
            log.info("found deployment [%s], belonging to def[%s]", dep.metadata.uid, definition.uid)
            return self._delete_deployment(dep)
        except InstanceNotFound:
            log.info('deployment belonging to def[%s] not found, assume it is already have been removed',
                     definition.uid)
            return True

    @run_in_executor
    def create_instance(self, definition: InstanceDefinition) -> Awaitable[Instance]:
        # noinspection PyTypeChecker
        return self._d2i(self._create_deployment(definition, replicas=0))

    @run_in_executor
    def launch_instance(self, definition: InstanceDefinition) -> Awaitable[Instance]:
        # noinspection PyTypeChecker
        return self._d2i(self._launch_instance(definition))

    @run_in_executor
    def stop_instance(self, definition: InstanceDefinition) -> Awaitable[bool]:
        # noinspection PyTypeChecker
        return self._stop_instance(definition)

    @run_in_executor
    def remove_instance(self, definition: InstanceDefinition) -> Awaitable[bool]:
        # noinspection PyTypeChecker
        return self._remove_instance(definition)
