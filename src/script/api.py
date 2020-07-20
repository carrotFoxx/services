import logging
from typing import List

import inject
import json
from aiohttp import hdrs
from aiohttp.web import UrlDispatcher, HTTPCreated
from aiohttp.web_exceptions import HTTPBadRequest, HTTPNoContent, HTTPNotFound, HTTPInternalServerError
from aiohttp.web_request import Request

from common.entities import RouteConfigWorkspace, RouteConfigConsumer, RouteConfigProducer, Workspace, Chain, \
    RouteConfig
from config import WSP_TYPE_PRODUCER, WSP_TYPE_WORKSPACE, WSP_TYPE_CONSUMER
from mco.rpc import RPCRoutable, RPCClient
from microcore.base.application import Routable
from microcore.base.repository import DoesNotExist, StorageException
from microcore.entity.encoders import json_response
from microcore.web.owned_api import OwnedReadWriteStorageAPI

log = logging.getLogger(__name__)

IF_MATCH = 'X-If-Version'


class ScriptAPI(Routable, RPCRoutable, OwnedReadWriteStorageAPI):
    wsp_manager: RPCClient = inject.attr('rpc_wsp_manager')
    entity_type = Chain

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def set_routes(self, router: UrlDispatcher):

        root = router.add_resource('/script/')
        root.add_route(hdrs.METH_GET, self.list_pageable)
        root.add_route(hdrs.METH_POST, self.post_chain)

        item = router.add_resource('/script/{id}')
        item.add_route(hdrs.METH_GET, self.get_chain)
        item.add_route(hdrs.METH_DELETE, self.delete_chain)
        item.add_route(hdrs.METH_PUT, self.change_chain)

    def set_methods(self) -> List[callable]:
        return [
        ]

    @json_response
    async def post_chain(self, request: Request):
        check = await self.check_request(request)
        if check != "ok":
            return HTTPBadRequest(reason=check)

        entity: Chain = await self._catch_input(request=request, transformer=self._post_transformer)
        wr_list = entity.wr  # wr - workspace + routes
        tmp_wsp_list = list()
        tmp_wr_list = list()
        for wr in wr_list:
            try:
                wsp_entity = await self.wsp_manager.post(wr["workspace"], request["owner_id"])
                tmp_wsp_list.append(wsp_entity)
                tmp_wr = dict()
                tmp_wr["workspace"] = wsp_entity
                tmp_wr["routes"] = wr["routes"]
                tmp_wr_list.append(tmp_wr)
            except:
                for wsp in tmp_wsp_list:
                    await self.wsp_manager.delete(wsp.uid)
                return HTTPBadRequest()

            wsp_type = wr["workspace"].get("type")
            try:
                if wsp_type == WSP_TYPE_CONSUMER:
                    data: RouteConfig = RouteConfigConsumer(wsp_uid=wsp_entity.uid, **wr["routes"])
                elif wsp_type == WSP_TYPE_PRODUCER:
                    data: RouteConfig = RouteConfigProducer(wsp_uid=wsp_entity.uid, **wr["routes"])
                elif wsp_type == WSP_TYPE_WORKSPACE:
                    data: RouteConfig = RouteConfigWorkspace(wsp_uid=wsp_entity.uid, **wr["routes"])
                await self.wsp_manager.reroute(workspace=wsp_entity, route=data)
            except:
                for wsp in tmp_wsp_list:
                    await self.wsp_manager.delete(wsp.uid)
                return HTTPBadRequest()
        entity.wr = tmp_wr_list
        await self.repository.save(entity)
        return HTTPCreated(text=json.dumps({'uid': entity.uid}))

    @json_response
    async def change_chain(self, request: Request):
        global route
        check = await self.check_request(request)
        if check != "ok":
            return HTTPBadRequest(reason=check)
        new_chain = Chain()
        put_chain = await request.json()
        if put_chain.get("name") is not None:
            new_chain.name = put_chain["name"]
        new_chain.uid = request.match_info['id']
        new_wsp_list = list()
        wr_list = list()
        workspaces = put_chain["wr"]
        for element in workspaces:
            try:
                workspace = element["workspace"]
                try:
                    tmp_wsp: Workspace = await self.wsp_manager.get(workspace["uid"])
                    workspace["created"] = tmp_wsp.created
                except:
                    pass
                wsp_entity = await self.wsp_manager.post(workspace, request["owner_id"])
                new_wsp_list.append(wsp_entity)
                wr = dict()
                wr["workspace"] = wsp_entity
            except:
                return HTTPBadRequest()

            routes = element["routes"]
            wr["routes"] = routes
            wr_list.append(wr)
            wspType: '' = workspace["type"]
            try:
                if wspType == WSP_TYPE_CONSUMER:
                    route = RouteConfigConsumer(wsp_uid=wsp_entity.uid, **routes)
                elif wspType == WSP_TYPE_PRODUCER:
                    route = RouteConfigProducer(wsp_uid=wsp_entity.uid, **routes)
                elif wspType == WSP_TYPE_WORKSPACE:
                    route = RouteConfigWorkspace(wsp_uid=wsp_entity.uid, **routes)
            except:
                for wsp in new_wsp_list:
                    try:
                        await self.wsp_manager.delete(wsp.uid)
                    except:
                        pass
                return HTTPBadRequest()
            await self.wsp_manager.reroute(workspace=wsp_entity, route=route)
        orig_chain = await self.repository.load(request.match_info['id'])
        for wr in orig_chain.wr:
            wsp = wr.get("workspace")
            delete_flag = True
            for new_wsp in new_wsp_list:
                if wsp.uid == new_wsp.uid:
                    delete_flag = False
                    break
            if delete_flag is True:
                if await self.check_workspace_chain_owners(wsp.uid, request):
                    return HTTPBadRequest(reason="Can't delete workspace, another chains are using it")
                try:
                    await self.wsp_manager.delete(wsp.uid)
                except:
                    pass
        new_chain.wr = wr_list
        new_chain.created = orig_chain.created
        await self.repository.save(new_chain)
        return new_chain

    @json_response
    async def get_chain(self, request: Request):
        return await self.repository.load(request.match_info['id'])

    @json_response
    async def delete_chain(self, request: Request):
        try:
            entity: Chain = await self.repository.load(request.match_info['id'])
        except DoesNotExist:
            raise HTTPNotFound()
        except StorageException as e:
            raise HTTPInternalServerError() from e
        wrList = entity.wr
        for wr in wrList:
            try:
                check = await self.check_workspace_chain_owners(wr["workspace"].uid, request)
                if check is False:
                    await self.wsp_manager.delete(wr["workspace"].uid)
                elif check is True:
                    return HTTPBadRequest(reason='Workspace using another chains')

            except:
                pass
        try:
            await self._delete(entity)
        except:
            raise HTTPNotFound()
        return HTTPNoContent()

    async def check_workspace_chain_owners(self, workspace_uid, request: Request):
        chain_entit_list = await self._list(await self._list_query(request))
        for entity in chain_entit_list:
            if entity.uid != request.match_info['id']:
                for element in entity.wr:
                    if workspace_uid == element.get("workspace").uid:
                        return True
        return False

    async def check_request(self, request: Request):
        err_list = list()
        body: dict = await request.json()
        if body.get("wr") is None:
            err_list.append("no workspaces and routes list")
        wrs: dict = body["wr"]
        for wr in wrs:
            if wr.get("workspace") is None or wr.get("routes") is None:
                err_list.append("no workspace or routes")
            wsp = wr["workspace"]
            if wsp.get("uid") is None:
                err_list.append("no workspace uid")
            wsp_check = self.check_workspace_body(wsp)
            if wsp_check != "ok":
                err_list.append(wsp_check)
            routes = wr["routes"]
            if routes.get("pause_stream") is None:
                err_list.append("no pause_stream")
            wsp_type = wsp.get("type")
            if wsp_type == "producer":
                if routes.get("incoming_stream") is not None or routes.get("outgoing_stream") is None:
                    err_list.append("wrong producer routes")
            if wsp_type == "workspace":
                if routes.get("outgoing_stream") is None or routes.get("incoming_stream") is None:
                    err_list.append("wrong workspaces routes")
            if wsp_type == "consumer":
                if routes.get("outgoing_stream") is not None or routes.get("incoming_stream") is None:
                    err_list.append("wrong consumer routes")
        if len(err_list) > 0:
            return err_list
        else:
            return "ok"

    def check_workspace_body(self, wsp):
        err_list = list()
        wsp_type = wsp.get("type")
        if wsp_type is None:
            err_list.append("no workspace type")
        if wsp_type != "producer" and wsp_type != "workspace" and wsp_type != "consumer":
            err_list.append("wrong workspace type")
        if wsp.get("app_id") is None:
            err_list.append("no wsp app_id")
        if wsp.get("app_ver") is None:
            err_list.append("no wsp app_ver")
        if wsp.get("model_id") is None:
            err_list.append("no wsp model_id")
        if wsp.get("model_ver") is None:
            err_list.append("no wsp model_ver")
        if len(err_list) > 0:
            return err_list
        else:
            return "ok"