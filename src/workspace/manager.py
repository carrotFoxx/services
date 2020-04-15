import asyncio
import hashlib
import logging
from typing import Awaitable, Dict, List

import inject
from aiohttp_json_rpc import RpcGenericServerDefinedError

from common.consul import ConsulClient
from common.entities import App, Model, Workspace
from config import CONSUL_DSN, KAFKA_DSN
from container_manager.attachment import AttachmentPrefix
from container_manager.definitions import Instance, InstanceDefinition
from mco.rpc import RPCClient
from microcore.base.repository import Repository
from workspace.configurator import Configurator

logger = logging.getLogger(__name__)


class WorkspaceManager:
    rpc_applications: RPCClient = inject.attr('rpc_app_manager')
    rpc_models: RPCClient = inject.attr('rpc_model_manager')
    rpc_environments: RPCClient = inject.attr('rpc_env_manager')
    consul: ConsulClient = inject.attr(ConsulClient)

    def __init__(self, workspaces: Repository, loop=None) -> None:
        super().__init__()
        self._loop = loop or asyncio.get_event_loop()
        self.workspaces = workspaces
        self.configurator = Configurator(consul=self.consul)

    @staticmethod
    def _get_hashed_id(*args) -> str:
        hash_func = hashlib.sha1()
        for x in args:
            hash_func.update(bytes(str(x), encoding='utf-8'))
        return hash_func.hexdigest()

    @staticmethod
    def _check_app_ref(ref: str):
        try:
            p = AttachmentPrefix.check(ref)
        except ValueError:
            raise RuntimeError('invalid attachment type')
        logger.info('creating definition with provider %s', p)

    def _create_definition(self, workspace: Workspace, app: App, model: Model) -> InstanceDefinition:
        image = app.attachment
        # check image ref format
        self._check_app_ref(image)
        attachments = {}
        if model and model.attachment is not None:
            attachments = {
                '/var/model': model.attachment
            }
        instance_id = self._get_hashed_id(workspace.uid, workspace.type, app.uid, app.version, model.uid, model.version)

        return InstanceDefinition(
            uid=instance_id,
            image=image,
            attachments=attachments,
            environment={
                **app.environment,
                'BDZ_NODE_ID': workspace.uid,
                'BDZ_CONSUL_DSN': CONSUL_DSN,
                'BDZ_KAFKA_DSN': KAFKA_DSN,
            },
            labels={
                'wsp_id': workspace.uid,
                'type': workspace.type,
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


    def get_route_config(self, workspace: Workspace):
        return self.configurator.read(workspace)

    def reroute(self, workspace: Workspace, route):
        route.wsp_uid = workspace.uid
        return self.configurator.write(route)

    async def _get_wsp_meta(self, workspace):
        try:
            logger.debug('gathering workspace info')
            app: App = await self.rpc_applications.get_version(workspace.app_id, workspace.app_ver)
            model: Model = await self.rpc_models.get_version(workspace.model_id, workspace.model_ver)
        except RpcGenericServerDefinedError as e:
            raise RuntimeError('failed to gather env metadata: %s', e.message)
        return app, model

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

    async def decommission(self, workspace: Workspace):
        if workspace.instance_id is None:
            raise ValueError('not provisioned')
        definition = await self.get_definition(workspace)
        logger.info('decommissioning workspace: %s', workspace)
        await self.rpc_environments.remove_app_instance(definition)
        await self.configurator.clear(workspace.uid)

    async def schedule_gc(self, workspace: Workspace):
        # todo: schedule GC
        logger.debug('scheduling gc for %s', workspace)

    async def healthcheck(self, workspace: Workspace) -> List[Dict[str, str]]:
        _, checks = await self.consul.official.health.checks('bdz-wsp-%s' % workspace.uid)
        if checks is None or len(checks) == 0:
            return [
                {"id": "-missing-",
                 "name": "-missing-",
                 "status": "not running",
                 "output": "404: checks not found"}
            ]
        # shorted consul response, stripping off unrelated parts
        return [
            {"id": c["CheckID"],
             "name": c["Name"],
             "status": c["Status"],
             "output": c["Output"]}
            for c in checks
        ]
