import logging
from typing import List

import inject
from aiohttp import hdrs
from aiohttp.web import UrlDispatcher, HTTPCreated
from aiohttp.web_exceptions import HTTPBadRequest, HTTPNoContent, HTTPNotFound, HTTPInternalServerError
from aiohttp.web_request import Request

from common.entities import RouteConfigWorkspace, RouteConfigConsumer, RouteConfigProducer, Workspace, Manifest, \
    RouteConfig, Resource
from config import WSP_TYPE_PRODUCER, WSP_TYPE_WORKSPACE, WSP_TYPE_CONSUMER
from mco.rpc import RPCRoutable, RPCClient
from microcore.base.application import Routable
from microcore.base.repository import DoesNotExist, StorageException
from microcore.entity.encoders import json_response, proxy_encoder_instance
from microcore.entity.model import JSON_TYPE_FIELD
from microcore.web.owned_api import OwnedReadWriteStorageAPI, OWNER_ID

log = logging.getLogger(__name__)

IF_MATCH = 'X-If-Version'


class ScriptAPI(Routable, RPCRoutable, OwnedReadWriteStorageAPI):
    wsp_manager: RPCClient = inject.attr('rpc_wsp_manager')
    entity_type = Manifest

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def set_routes(self, router: UrlDispatcher):

        root = router.add_resource('/scripts')
        root.add_route(hdrs.METH_GET, self.list_pageable)
        root.add_route(hdrs.METH_POST, self.post_manifest_new)

        item = router.add_resource('/scripts/{id}')
        item.add_route(hdrs.METH_GET, self.get_manifest)
        item.add_route(hdrs.METH_DELETE, self.delete_manifest)

    def set_methods(self) -> List[callable]:
        return [
        ]

    @json_response
    async def post_manifest_new(self, request: Request):
        manifest = self._decode_payload(await request.json())
        res = manifest.resources
        wsps_uid = list()
        channels = dict()
        resources = list()
        for r in res:
            resourse_entity = self.entity_decode_payload(r, Resource)
            resources.append(resourse_entity)
            if resourse_entity.clss == "channel":
                channels[resourse_entity.label] = resourse_entity.properties

        for resourse_entity in resources:
            global incoming_key, outgoing_key
            if resourse_entity.clss == WSP_TYPE_PRODUCER or resourse_entity.clss == WSP_TYPE_WORKSPACE or resourse_entity.clss == WSP_TYPE_CONSUMER:
                try:
                    wsp: Workspace = await self.create_wsp_from_resource(resourse_entity, request)
                    resourse_entity.properties['uid'] = wsp.uid
                    wsps_uid.append(wsp.uid)
                except Exception as e:
                    await self.delete_wsps(wsps_uid, request)
                    return HTTPBadRequest(reason=e)

                routes = dict()
                routes['pause_stream'] = resourse_entity.properties['pause_stream']
                try:
                    if resourse_entity.clss == WSP_TYPE_CONSUMER:
                        incoming_key = resourse_entity.routes.get("incoming")[0].get('ref')
                        try:
                            routes['incoming_stream'] = channels[incoming_key].get('kafka_topic')
                        except:
                            raise Exception(incoming_key)
                        route_data: RouteConfig = RouteConfigConsumer(wsp_uid=wsp.uid, **routes)

                    elif resourse_entity.clss == WSP_TYPE_PRODUCER:
                        outgoing_key = resourse_entity.routes.get("outgoing")[0].get('ref')
                        try:
                            routes['outgoing_stream'] = channels[outgoing_key].get('kafka_topic')
                        except:
                            raise Exception(outgoing_key)
                        route_data: RouteConfig = RouteConfigProducer(wsp_uid=wsp.uid, **routes)

                    elif resourse_entity.clss == WSP_TYPE_WORKSPACE:
                        incoming_key = resourse_entity.routes.get("incoming")[0].get('ref')
                        outgoing_key = resourse_entity.routes.get("outgoing")[0].get('ref')
                        try:
                            routes['incoming_stream'] = channels[incoming_key].get('kafka_topic')
                        except:
                            raise Exception(incoming_key)
                        try:
                            routes['outgoing_stream'] = channels[outgoing_key].get('kafka_topic')
                        except:
                            raise Exception(outgoing_key)
                        route_data: RouteConfig = RouteConfigWorkspace(wsp_uid=wsp.uid, **routes)
                    await self.wsp_manager.reroute(workspace=wsp, route=route_data)
                except Exception as e:
                    await self.delete_wsps(wsps_uid, request)
                    return HTTPBadRequest(reason="invalid link: " + str(e))
            elif resourse_entity.clss != 'channel':
                await self.delete_wsps(wsps_uid, request)
                return HTTPBadRequest(reason="invalid workspace type: " + str(resourse_entity.clss))
        manifest.resources = resources
        manifest.set_owner(request[OWNER_ID])
        await self.repository.save(manifest)
        response = dict()
        response["uid"] = manifest.uid
        healths = list()
        for uid in wsps_uid:
            result = dict()
            result['id'] = uid
            try:
                entity = await self.wsp_manager.get(uid)
            except:
                result['status'] = "workspace is not exist"
                continue
            health = await self.wsp_manager.health(entity)
            if health[0].get("status") == "not running":
                result['status'] = "creation in progess"
            elif health[0].get("status") != "not running":
                result['status'] = health[0].get("status")
            healths.append(result)
        response['wsps health'] = healths
        return response

    def entity_decode_payload(self, raw: dict, entity_type):  # -> entity_type:
        raw.pop(JSON_TYPE_FIELD, None)  # fixes issue if we query our own APIs with __type__'ed objects
        decoded = proxy_encoder_instance.get_encoder_for_type(entity_type).unpack(raw, entity_type)
        assert isinstance(decoded, entity_type)
        return decoded

    async def create_wsp_from_resource(self, resourse_entity: Resource, request):
        try:
            json_wrsp = dict()
            if resourse_entity.properties.get('uid') != None and resourse_entity.properties.get('uid') != '':
                json_wrsp['uid'] = resourse_entity.properties.get('uid')
            if resourse_entity.properties.get('name') == '':
                raise
            else:
                json_wrsp['name'] = resourse_entity.properties.get('name')
            json_wrsp['type'] = resourse_entity.properties.get('clss')
            json_wrsp['app_id'] = resourse_entity.properties.get('application').get('id')
            json_wrsp['app_ver'] = resourse_entity.properties.get('application').get('version')
            json_wrsp['model_id'] = resourse_entity.properties.get('model').get('id')
            json_wrsp['model_ver'] = resourse_entity.properties.get('model').get('version')
            json_wrsp['owner'] = request["owner_id"]
            json_wrsp['type'] = resourse_entity.clss
        except:
            raise Exception("invalid request struct")
        try:
            wsp_entity = self.entity_decode_payload(json_wrsp, Workspace)
            await self.wsp_manager.post(wsp_entity)
        except:
            raise Exception("error create workspace")
        return wsp_entity

    async def delete_wsps(self, wsps_uid: List, request: Request):
        manifests = await self._list(await self._list_query(request))
        busy_wsps_uid = list()
        for manifest in manifests:
            for entity in manifest.resources:
                if entity.clss == WSP_TYPE_PRODUCER or entity.clss == WSP_TYPE_WORKSPACE or entity.clss == WSP_TYPE_CONSUMER:
                    busy_wsps_uid.append(entity.properties['uid'])
        for wsp_uid in wsps_uid:
            delete_flag = True
            for busy_uid in busy_wsps_uid:
                if wsp_uid == busy_uid:
                    delete_flag = False
            if delete_flag == True:
                await self.wsp_manager.async_delete(wsp_uid)

    @json_response
    async def get_manifest(self, request: Request):
        return await self.repository.load(request.match_info['id'])

    @json_response
    async def delete_manifest(self, request: Request):
        wsps_uid = list()
        try:
            manifest: Manifest = await self.repository.load(request.match_info['id'])
        except DoesNotExist:
            return HTTPNotFound()
        entitys = manifest.resources
        for entity in entitys:
            if entity.clss == WSP_TYPE_WORKSPACE or entity.clss == WSP_TYPE_CONSUMER or entity.clss == WSP_TYPE_PRODUCER:
                wsps_uid.append(entity.properties['uid'])
        await self.repository.delete(request.match_info['id'])
        await self.delete_wsps(wsps_uid, request)
        return HTTPNoContent()