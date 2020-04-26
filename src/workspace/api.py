import asyncio
import logging
from typing import List

from aiohttp import hdrs
from aiohttp.web import UrlDispatcher
from aiohttp.web_exceptions import HTTPBadRequest, HTTPNoContent, HTTPNotFound, HTTPInternalServerError
from aiohttp.web_request import Request

from common.entities import RouteConfigWorkspace, RouteConfigConsumer, RouteConfigProducer, Workspace, \
    WorkspaceNeighbors, WorkspacesChain
from config import WSP_TYPE_PRODUCER, WSP_TYPE_WORKSPACE, WSP_TYPE_CONSUMER
from mco.rpc import RPCRoutable, rpc_expose
from microcore.base.application import Routable
from microcore.base.repository import DoesNotExist
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
        root.add_route(hdrs.METH_POST, self.post)

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
            rpc_expose(self.repository.load, name='get')
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

    async def _provisioning_task(self, workspace: Workspace):
        try:
            await self.manager.provision(workspace)
        except:
            log.exception('provisioning failed, deleting workspace')
            await self.repository.delete(workspace.uid)

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
            centerWrks: Workspace = await self._get(request)
        except DoesNotExist:
            raise HTTPNotFound

        try:
            lst = await self._list(await self._list_query(request))
        except AttributeError as e:
            raise HTTPBadRequest() from e

        centerWorkspRoutes: RouteConfigWorkspace = await self.manager.get_route_config(centerWrks)

        incomingNeighbors = list()
        outgoingNeighbors = list()
        for workspace in lst:
            routes: RouteConfigWorkspace = await self.manager.get_route_config(workspace)
            if workspace.type != WSP_TYPE_CONSUMER and centerWrks.type!=WSP_TYPE_PRODUCER:
                if centerWorkspRoutes.incoming_stream == routes.outgoing_stream and centerWrks.uid != workspace.uid:
                    incomingNeighbors.append(workspace.uid)
            if workspace.type != WSP_TYPE_PRODUCER and centerWrks.type!=WSP_TYPE_CONSUMER:
                if centerWorkspRoutes.outgoing_stream == routes.incoming_stream and centerWrks.uid != workspace.uid:
                    outgoingNeighbors.append(workspace.uid)

        data = WorkspaceNeighbors(incomingNeighbors, outgoingNeighbors)
        return data

    @json_response
    async def get_chain(self, request: Request):

        producerRoute: RouteConfigWorkspace
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

        envWrspList = list()
        for workspace in lst:
            if workspace.type != WSP_TYPE_PRODUCER and producerRoute.outgoing_stream == routesList.get(workspace.uid).incoming_stream:
                envWrspList.append(workspace.uid)

        graph.update({producerWsp.uid: envWrspList})

        for nodeWorkspace in lst:
            if nodeWorkspace.type != WSP_TYPE_PRODUCER and nodeWorkspace.type != WSP_TYPE_CONSUMER:
                envWrspList = list()
                nodeRoutes: RouteConfigWorkspace = routesList.get(nodeWorkspace.uid)
                for envWorkspace in lst:
                    if envWorkspace.type != WSP_TYPE_PRODUCER:
                        if nodeRoutes.outgoing_stream == routesList.get(envWorkspace.uid).incoming_stream:
                            envWrspList.append(envWorkspace.uid)
                graph.update({nodeWorkspace.uid: envWrspList})

        data = WorkspacesChain(graph)
        return data
