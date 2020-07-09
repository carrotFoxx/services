import logging
from typing import List

import inject
import json
from aiohttp import hdrs
from aiohttp.web import UrlDispatcher, HTTPCreated
from aiohttp.web_exceptions import HTTPBadRequest, HTTPNoContent, HTTPNotFound, HTTPInternalServerError
from aiohttp.web_request import Request

from common.entities import RouteConfigWorkspace, RouteConfigConsumer, RouteConfigProducer, Workspace, Chain, RouteConfig
from config import WSP_TYPE_PRODUCER, WSP_TYPE_WORKSPACE, WSP_TYPE_CONSUMER
from mco.rpc import RPCRoutable, rpc_expose, RPCClient
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

        root = router.add_resource('/chains')
        root.add_route(hdrs.METH_GET, self.list_pageable)

        crChain = router.add_resource('/script/chain')
        crChain.add_route(hdrs.METH_POST, self.post_chain)
        crChain.add_route(hdrs.METH_PUT, self.change_chain)

        item = router.add_resource('/script/{id}')
        item.add_route(hdrs.METH_GET, self.get_chain)
        item.add_route(hdrs.METH_DELETE, self.delete)


    def set_methods(self) -> List[callable]:
        return [
            rpc_expose(self.repository.load, name='get')
        ]

    @json_response
    async def post_chain(self, request: Request):
        entity: Chain = await self._catch_input(request=request, transformer=self._post_transformer)
        wrList = entity.wr #wr - workspace + routes
        tmpWspList = list()
        tmpWrList = list()
        for wr in wrList:
            try:
                wspEntity = await self.wsp_manager.post(wr["workspace"], request["owner_id"])
                tmpWspList.append(wspEntity)
                tmpWr = dict()
                tmpWr["workspace"] = wspEntity
                tmpWr["routes"] = wr["routes"]
                tmpWrList.append(tmpWr)
            except:
                for wsp in tmpWspList:
                    await self.wsp_manager.delete(wsp.uid)
                return HTTPBadRequest()

            wspType = wr["workspace"].get("type")
            try:
                if wspType == WSP_TYPE_CONSUMER:
                    data: RouteConfig = RouteConfigConsumer(wsp_uid=wspEntity.uid, **wr["routes"])
                elif wspType == WSP_TYPE_PRODUCER:
                    data: RouteConfig = RouteConfigProducer(wsp_uid=wspEntity.uid, **wr["routes"])
                elif wspType == WSP_TYPE_WORKSPACE:
                    data: RouteConfig = RouteConfigWorkspace(wsp_uid=wspEntity.uid, **wr["routes"])
                await self.wsp_manager.reroute(workspace=wspEntity, route=data)
            except:
                for wsp in tmpWspList:
                    await self.wsp_manager.delete(wsp.uid)
                return HTTPBadRequest()
        entity.wr = tmpWrList
        await self.repository.save(entity)
        return HTTPCreated(text=json.dumps({'uid': entity.uid}))

    @json_response
    async def change_chain(self, request: Request):

        newChain = Chain(None)
        putChain = await request.json()
        if putChain.get("uid") == None:
            return HTTPBadRequest()
        newChain.uid = putChain["uid"]

        if putChain.get("name") != None:
            newChain.name = putChain["name"]

        newWspList = list()
        wrList = list()
        workspaces = putChain["wr"]
        for element in workspaces:
            try:
                workspace = element["workspace"]
                try:
                    tmp_wsp: Workspace = await self.wsp_manager.get(workspace["uid"])
                    if workspace.get("name") == None:
                        workspace["name"] = tmp_wsp.name

                    if workspace.get("type") == None:
                        workspace["type"] = tmp_wsp.type

                    if workspace.get("app_id") == None:
                        workspace["app_id"] = tmp_wsp.app_id

                    if workspace.get("app_ver") == None:
                        workspace["app_ver"] = tmp_wsp.app_ver

                    if workspace.get("model_id") == None:
                        workspace["model_id"] = tmp_wsp.model_id

                    if workspace.get("model_ver") == None:
                        workspace["model_ver"] = tmp_wsp.model_ver

                    if workspace.get("created") == None:
                        workspace["created"] = tmp_wsp.created

                    if workspace.get("updated") == None:
                        workspace["updated"] = self._issue_ts().timestamp()
                except:
                    pass
                wspEntity = await self.wsp_manager.post(workspace, request["owner_id"])
                newWspList.append(wspEntity)
                wr = dict()
                wr["workspace"] = wspEntity
            except:
                return HTTPBadRequest()

            routes = element["routes"]
            wr["routes"] = routes
            wrList.append(wr)
            try:
                wspType = workspace["type"]
                if wspType != WSP_TYPE_PRODUCER and wspType != WSP_TYPE_WORKSPACE and wspType != WSP_TYPE_CONSUMER:
                    return HTTPBadRequest()
            except:
                pass
            try:
                if wspType == WSP_TYPE_CONSUMER:
                    data = RouteConfigConsumer(wsp_uid=wspEntity.uid, **routes)
                elif wspType == WSP_TYPE_PRODUCER:
                    data = RouteConfigProducer(wsp_uid=wspEntity.uid, **routes)
                elif wspType == WSP_TYPE_WORKSPACE:
                    data = RouteConfigWorkspace(wsp_uid=wspEntity.uid, **routes)
            except:
                for wsp in newWspList:
                    try:
                        await self.wsp_manager.delete(wsp.uid)
                    except:
                        pass
                return HTTPBadRequest()
            await self.wsp_manager.reroute(workspace=wspEntity, route=data)
        origChain = await self.repository.load(putChain.get("uid"))
        for wr in origChain.wr:
            wsp = wr.get("workspace")
            deleteFlag = True
            for newWsp in newWspList:
                if wsp.uid == newWsp.uid:
                    deleteFlag = False
                    break
            if deleteFlag == True:
                try:
                    await self.wsp_manager.delete(wsp.uid)
                except:
                    pass
        newChain.wr = wrList
        newChain.created = origChain.created
        await self.repository.save(newChain)
        return newChain

    @json_response
    async def get_chain(self, request: Request):
        return await self.repository.load(request.match_info['id'])

    @json_response
    async def delete(self, request: Request):
        try:
            entity: Chain = await self.repository.load(request.match_info['id'])
        except DoesNotExist:
            raise HTTPNotFound()
        except StorageException as e:
            raise HTTPInternalServerError() from e
        wrList = entity.wr
        for wr in wrList:
            try:
                answ = await self.check_worksapce_owners(wr["workspace"].uid,request)
                if answ == False:
                    await self.check_worksapce_owners(self, request)
                    await self.wsp_manager.delete(wr["workspace"].uid)
                elif answ == True:
                    return HTTPBadRequest(reason='workspace used another chains')

            except:
                pass
        try:
            await self._delete(entity)
        except:
            raise HTTPNotFound()
        return HTTPNoContent()

    async def check_worksapce_owners(self, workspace_uid, request: Request):
        chainEntitList = await self._list(await self._list_query(request))
        for entity in chainEntitList:
            if entity.uid != request.match_info['id']:
                for element in entity.wr:
                    if workspace_uid == element.get("workspace").uid:
                        return True
        return False
