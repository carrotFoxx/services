import asyncio
import json
import logging
from typing import List

from aiohttp import hdrs
from aiohttp.web import UrlDispatcher
from aiohttp.web_exceptions import HTTPBadRequest, HTTPNoContent, HTTPNotFound, HTTPInternalServerError, HTTPCreated
from aiohttp.web_request import Request

from common.entities import RouteConfigWorkspace, RouteConfigConsumer, RouteConfigProducer, Workspace, \
    WorkspaceNeighbors, WorkspacesChain
from config import WSP_TYPE_PRODUCER, WSP_TYPE_WORKSPACE, WSP_TYPE_CONSUMER
from mco.rpc import RPCRoutable, rpc_expose
from microcore.base.application import Routable
from microcore.base.repository import DoesNotExist, StorageException
from microcore.entity.abstract import Owned
from microcore.entity.encoders import json_response
from microcore.web.owned_api import OwnedReadWriteStorageAPI
from workspace.manager import WorkspaceManager

log = logging.getLogger(__name__)


class WorkspaceAPI(Routable, RPCRoutable, OwnedReadWriteStorageAPI):
    entity_type = Workspace

    def __init__(self, manager: WorkspaceManager, **kwargs):
        super().__init__(**kwargs)
        self.manager = manager

    def set_routes(self, router: UrlDispatcher):
        root = router.add_resource('/workspaces')
        root.add_route(hdrs.METH_HEAD, self.head_list)
        root.add_route(hdrs.METH_GET, self.list_pageable)
        root.add_route(hdrs.METH_POST, self.post_wsp)

        sync_root = router.add_resource('/workspaces/sync')
        sync_root.add_route(hdrs.METH_POST, self.sync_post_wsp)

        chain = router.add_resource('/workspaces/chain')
        chain.add_route(hdrs.METH_GET, self.get_chain)

        item = router.add_resource('/workspaces/{id}')
        item.add_route(hdrs.METH_GET, self.get)
        item.add_route(hdrs.METH_PUT, self.put)
        item.add_route(hdrs.METH_DELETE, self.delete)

        config = router.add_resource('/workspaces/{id}/route')
        config.add_route(hdrs.METH_PUT, self.set_route)
        config.add_route(hdrs.METH_GET, self.get_route)

        health = router.add_resource('/workspaces/{id}/health')
        health.add_route(hdrs.METH_GET, self.health)

        neighbors = router.add_resource('/workspaces/{id}/neighbors')
        neighbors.add_route(hdrs.METH_GET, self.get_neighbors)

    def set_methods(self) -> List[callable]:
        return [
            rpc_expose(self.repository.load, name='get'),
            rpc_expose(self.rpc_post, name='post'),
            rpc_expose(self.rpc_delete, name='delete'),
            rpc_expose(self.rpc_async_delete, name='async_delete'),
            rpc_expose(self.manager.reroute, name='reroute'),
            rpc_expose(self.rpc_health, name='health'),
            rpc_expose(self.repository.save, name='save')
        ]

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

    @json_response
    async def sync_post_wsp(self, request: Request):
        entity = await self._catch_input(request=request, transformer=self._post_transformer)
        if not isinstance(entity, Workspace):
            raise HTTPBadRequest()
        if entity.type != WSP_TYPE_PRODUCER and entity.type != WSP_TYPE_WORKSPACE and entity.type != WSP_TYPE_CONSUMER:
            raise HTTPBadRequest()
        try:
            await super()._post(entity)
        except StorageException as e:
            raise HTTPInternalServerError() from e
        try:
            await self._provisioning_task(entity)
        except Exception as e:
            return HTTPBadRequest(reason=e)
        return HTTPCreated(text=json.dumps({'uid': entity.uid}))

    async def _provisioning_task(self, workspace: Workspace):
        try:
            await self.manager.provision(workspace)
        except:
            log.exception('provisioning failed, deleting workspace')
            asyncio.create_task(self.repository.delete(workspace.uid))
            raise Exception('provisioning failed, deleting workspace')

    @json_response
    async def post_wsp(self, request: Request):
        entity = await self._catch_input(request=request, transformer=self._post_transformer)
        if not isinstance(entity, Workspace):
            raise HTTPBadRequest()
        if entity.type != WSP_TYPE_PRODUCER and entity.type != WSP_TYPE_WORKSPACE and entity.type != WSP_TYPE_CONSUMER:
            raise HTTPBadRequest()
        return await self.post(request)

    async def set_route(self, request: Request):
        entity: Workspace = await self._get(request)
        try:
            if entity.type == WSP_TYPE_CONSUMER:
                data = RouteConfigConsumer(wsp_uid=entity.uid, **await request.json())
            elif entity.type == WSP_TYPE_PRODUCER:
                data = RouteConfigProducer(wsp_uid=entity.uid, **await request.json())
            elif entity.type == WSP_TYPE_WORKSPACE:
                data = RouteConfigWorkspace(wsp_uid=entity.uid, **await request.json())
        except (TypeError, ValueError) as e:
            raise HTTPBadRequest() from e
        await self.manager.reroute(workspace=entity, route=data)
        raise HTTPNoContent()

    @json_response
    async def get_route(self, request: Request):
        try:
            entity: Workspace = await self._get(request)
        except DoesNotExist:
            raise HTTPNotFound
        try:
            if entity.type == WSP_TYPE_CONSUMER:
                data: RouteConfigConsumer = await self.manager.get_route_config(entity)
            elif entity.type == WSP_TYPE_PRODUCER:
                data: RouteConfigProducer = await self.manager.get_route_config(entity)
            elif entity.type == WSP_TYPE_WORKSPACE:
                data: RouteConfigWorkspace = await self.manager.get_route_config(entity)
            else:
                raise HTTPInternalServerError()
        except self.manager.consul.InteractionError:
            data = RouteConfigWorkspace(wsp_uid=entity.uid)
        return data

    @json_response
    async def health(self, request: Request):
        try:
            entity: Workspace = await self._get(request)
        except DoesNotExist:
            raise HTTPNotFound
        return await self.manager.healthcheck(entity)

    @json_response
    async def get_neighbors(self, request: Request):
        try:
            centerWsp: Workspace = await self._get(request)
        except DoesNotExist:
            raise HTTPNotFound

        try:
            lst = await self._list(await self._list_query(request))
        except AttributeError as e:
            raise HTTPBadRequest() from e

        centerWspRoutes: RouteConfigWorkspace = await self.manager.get_route_config(centerWsp)

        incomingNeighbors = list()
        outgoingNeighbors = list()
        for workspace in lst:
            routes: RouteConfigWorkspace = await self.manager.get_route_config(workspace)
            if workspace.type != WSP_TYPE_CONSUMER and centerWsp.type!=WSP_TYPE_PRODUCER:
                if centerWspRoutes.incoming_stream == routes.outgoing_stream and centerWsp.uid != workspace.uid:
                    incomingNeighbors.append(workspace.uid)
            if workspace.type != WSP_TYPE_PRODUCER and centerWsp.type!=WSP_TYPE_CONSUMER:
                if centerWspRoutes.outgoing_stream == routes.incoming_stream and centerWsp.uid != workspace.uid:
                    outgoingNeighbors.append(workspace.uid)

        data = WorkspaceNeighbors(incomingNeighbors, outgoingNeighbors)
        return data

    @json_response
    async def get_chain(self, request: Request):

        producerRoute: RouteConfigWorkspace = None
        producerWsp: Workspace
        routesList = dict()
        graph = dict()

        try:
            lst = await self._list(await self._list_query(request))
        except AttributeError as e:
            raise HTTPBadRequest() from e

        for workspace in lst:
            routes: RouteConfigWorkspace = await self.manager.get_route_config(workspace)
            routesList.update({workspace.uid: routes})
            if workspace.type == WSP_TYPE_PRODUCER:
                producerRoute = routes
                producerWsp = workspace

        envWspList = list()
        for workspace in lst:
            if producerRoute != None and workspace.type != WSP_TYPE_PRODUCER and producerRoute.outgoing_stream == routesList.get(workspace.uid).incoming_stream:
                envWspList.append(workspace.uid)
        if (producerRoute != None):
            graph.update({producerWsp.uid: envWspList})

        for nodeWorkspace in lst:
            if nodeWorkspace.type != WSP_TYPE_PRODUCER and nodeWorkspace.type != WSP_TYPE_CONSUMER:
                envWspList = list()
                nodeRoutes: RouteConfigWorkspace = routesList.get(nodeWorkspace.uid)
                for envWorkspace in lst:
                    if envWorkspace.type != WSP_TYPE_PRODUCER:
                        if nodeRoutes.outgoing_stream == routesList.get(envWorkspace.uid).incoming_stream:
                            envWspList.append(envWorkspace.uid)
                graph.update({nodeWorkspace.uid: envWspList})

        data = WorkspacesChain(graph)
        return data

    async def rpc_post(self, workspace: Workspace):
        await self._post(workspace)

    async def rpc_delete(self, uid):
        stored = await self.repository.load(uid)
        await self._delete(stored)

    async def rpc_async_delete(self, uid):
        stored = await self.repository.load(uid)
        asyncio.create_task(self._delete(stored))

    async def rpc_health(self, workspace: Workspace) -> object:
        return await self.manager.healthcheck(workspace)