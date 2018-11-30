import asyncio
import logging

from aiohttp import hdrs
from aiohttp.web import UrlDispatcher
from aiohttp.web_exceptions import HTTPBadRequest, HTTPNoContent
from aiohttp.web_request import Request

from common.entities import RouteConfig, Workspace
from microcore.base.application import Routable
from microcore.entity.encoders import json_response
from microcore.web.owned_api import OwnedReadWriteStorageAPI
from workspace.manager import WorkspaceManager

log = logging.getLogger(__name__)


class WorkspaceAPI(Routable, OwnedReadWriteStorageAPI):
    entity_type = Workspace

    def __init__(self, manager: WorkspaceManager, **kwargs):
        super().__init__(**kwargs)
        self.manager = manager

    def set_routes(self, router: UrlDispatcher):
        root = router.add_resource('/workspaces')
        root.add_route(hdrs.METH_HEAD, self.head_list)
        root.add_route(hdrs.METH_GET, self.list)
        root.add_route(hdrs.METH_POST, self.post)

        item = router.add_resource('/workspaces/{id}')
        item.add_route(hdrs.METH_GET, self.get)
        item.add_route(hdrs.METH_PUT, self.put)
        item.add_route(hdrs.METH_DELETE, self.delete)

        config = router.add_resource('/workspaces/{id}/route')
        config.add_route(hdrs.METH_PUT, self.set_route)
        config.add_route(hdrs.METH_GET, self.get_route)

    async def _delete(self, stored: entity_type):
        try:
            await self.manager.decommission(stored)
        except ValueError:
            pass
        await self.repository.delete(stored.uid)

    async def _post(self, entity: Workspace):
        # save on provisioning success
        await super()._post(entity)
        # noinspection PyAsyncCall
        asyncio.create_task(self._provisioning_task(entity))

    async def _provisioning_task(self, workspace: Workspace):
        try:
            await self.manager.provision(workspace)
        except:
            log.exception('provisioning failed, deleting workspace')
            await self.repository.delete(workspace.uid)

    async def set_route(self, request: Request):
        entity: Workspace = await self._get(request)
        try:
            data = RouteConfig(wsp_uid=entity.uid, **await request.json())
        except (TypeError, ValueError) as e:
            raise HTTPBadRequest() from e
        await self.manager.reroute(workspace=entity, route=data)
        raise HTTPNoContent()

    @json_response
    async def get_route(self, request: Request):
        entity: Workspace = await self._get(request)
        try:
            data: RouteConfig = await self.manager.get_route_config(entity)
        except self.manager.consul.InteractionError:
            data = RouteConfig(wsp_uid=entity.uid)
        return data
