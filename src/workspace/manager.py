import asyncio
import hashlib
import logging

import attr
import inject
from aiohttp_json_rpc import RpcGenericServerDefinedError

from common.consul import ConsulClient, consul_key
from common.entities import App, Model, Workspace
from config import CONSUL_SUBORDINATE_DIR
from container_manager.definition import Instance, InstanceDefinition
from mco.rpc import RPCClient
from microcore.base.repository import Repository
from supervisor.state import ADOPTED_VERSION, DESIRED_VERSION

logger = logging.getLogger(__name__)


class WorkspaceManager:
    rpc_applications: RPCClient = inject.attr('rpc_app_manager')
    rpc_models: RPCClient = inject.attr('rpc_model_manager')
    rpc_environments: RPCClient = inject.attr('rpc_env_manager')
    consul: ConsulClient = inject.attr('consul')

    def __init__(self, workspaces: Repository, loop=None) -> None:
        super().__init__()
        self._loop = loop or asyncio.get_event_loop()
        self.workspaces = workspaces

    @staticmethod
    def _get_hashed_id(*args) -> str:
        hash_func = hashlib.sha1()
        for x in args:
            hash_func.update(bytes(str(x), encoding='utf-8'))
        return hash_func.hexdigest()

    def _create_definition(self, workspace: Workspace, app: App, model: Model) -> InstanceDefinition:
        image = app.package
        attachments = {}
        if model and model.attachment is not None:
            attachments = {
                '/var/model': model.attachment
            }
        instance_id = self._get_hashed_id(workspace.uid, app.uid, app.version, model.uid, model.version)

        return InstanceDefinition(
            uid=instance_id,
            image=image,
            attachments=attachments,
            environment={
                'BDZ_NODE_ID': workspace.uid,
                **app.environment
            },
            labels={
                'wsp_id': workspace.uid,
                'app_id': app.uid,
                'app_ver': app.version,
                'model_id': model.uid,
                'model_ver': model.version
            }
        )

    async def get_definition(self, workspace: Workspace) -> InstanceDefinition:
        app, model = await self._get_wsp_meta(workspace)
        definition = self._create_definition(workspace=workspace, app=app, model=model)
        return definition

    async def get_adopted_version(self, workspace: Workspace) -> int:
        return int(await self.consul.kv().get(
            consul_key(CONSUL_SUBORDINATE_DIR, workspace.uid, ADOPTED_VERSION),
            raw=True,
            default=0
        ))

    async def reroute(self, workspace: Workspace):
        """
        this is client part of supervisor.state.StateMonitor

        updates/creates node config in consul KV-store so supervisor could read it and configure itself
        """
        kv = self.consul.kv()
        desired_version: int = int(await kv.get(
            key=consul_key(CONSUL_SUBORDINATE_DIR, workspace.uid, DESIRED_VERSION),
            raw=True,
            default=0
        ))
        desired_version += 1  # increment to signal rerouting
        workspace.route_conf.desired_version = desired_version
        props = attr.asdict(workspace.route_conf)
        await asyncio.gather(*[
            kv.put(key=consul_key(CONSUL_SUBORDINATE_DIR, workspace.uid, key), value=value)
            for key, value in props.items()
        ])

    async def provision(self, workspace: Workspace):
        logger.info('scheduling a provision on %s', workspace)
        definition = await self.get_definition(workspace)
        logger.debug('creating environment')
        instance: Instance = await self.rpc_environments.create_app_instance(definition)
        logger.info('environment for %s created: %s', workspace, instance)
        workspace.instance_id = instance.uid
        logger.debug('patching workspace: %s', workspace)
        await self.workspaces.patch(workspace, only=('instance_id', 'updated'))
        return instance

    async def _get_wsp_meta(self, workspace):
        try:
            logger.debug('gathering workspace info')
            app: App = await self.rpc_applications.get_version(workspace.app_id, workspace.app_ver)
            model: Model = await self.rpc_models.get_version(workspace.model_id, workspace.model_ver)
        except RpcGenericServerDefinedError as e:
            raise RuntimeError('failed to gather env metadata: %s', e.message)
        return app, model

    async def decommission(self, workspace: Workspace):
        if workspace.instance_id is None:
            raise ValueError('not provisioned')
        definition = await self.get_definition(workspace)
        logger.info('decommissioning workspace: %s', workspace)
        await self.rpc_environments.remove_app_instance(definition)
        # drop routing config from consul kv-store
        await self.consul.kv().rem(consul_key(CONSUL_SUBORDINATE_DIR, workspace.uid), recurse=True)

    async def schedule_gc(self, workspace: Workspace):
        # todo: schedule GC
        logger.debug('scheduling gc for %s', workspace)
