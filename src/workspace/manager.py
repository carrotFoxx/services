import asyncio
import logging

import inject
from aiohttp_json_rpc import RpcGenericServerDefinedError

from common.entities import App, Model, Workspace
from container_manager.definition import Instance
from mco.rpc import RPCClient
from microcore.base.repository import Repository
from microcore.entity.bases import DateTimePropertyHelperMixin

logger = logging.getLogger(__name__)


class WorkspaceManager(DateTimePropertyHelperMixin):
    rpc_applications: RPCClient = inject.attr('rpc_app_manager')
    rpc_models: RPCClient = inject.attr('rpc_model_manager')
    rpc_environments: RPCClient = inject.attr('rpc_env_manager')

    def __init__(self, workspaces: Repository, loop=None) -> None:
        super().__init__()
        self._loop = loop or asyncio.get_event_loop()
        self.workspaces = workspaces

    async def provision(self, workspace: Workspace):
        logger.info('scheduling a provision on %s', workspace)
        app, model = await self._get_wsp_meta(workspace)
        logger.debug('creating environment')
        instance: Instance = await self.rpc_environments.create_app_instance(app=app, model=model)
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
        app, model = self._get_wsp_meta(workspace)
        return await self.rpc_environments.remove_app_instance(app=app, model=model)

    async def schedule_gc(self, workspace: Workspace):
        # todo: schedule GC
        logger.debug('scheduling gc for %s', workspace)
