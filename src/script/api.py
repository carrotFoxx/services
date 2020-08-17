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
    """ Class for working with json manifests

    """

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
        item.add_route(hdrs.METH_PUT, self.change_manifest)

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
                    wsp: Workspace = self.extract_workspace(resourse_entity, request)
                    await self.wsp_manager.post(wsp)
                    resourse_entity.properties['uid'] = wsp.uid
                    wsps_uid.append(wsp.uid)
                except Exception as e:
                    await self.delete_wsps(wsps_uid, request)
                    return HTTPBadRequest(reason=e)
                try:
                    route_data = self.extract_route(resourse_entity, channels)
                    await self.wsp_manager.reroute(workspace=wsp, route=route_data)
                except Exception as e:
                    await self.delete_wsps(wsps_uid, request, None)
                    return HTTPBadRequest(reason="invalid link: " + str(e))
            elif resourse_entity.clss != 'channel':
                await self.delete_wsps(wsps_uid, request, None)
                return HTTPBadRequest(reason="invalid workspace type: " + str(resourse_entity.clss))
        manifest.resources = resources
        manifest.set_owner(request[OWNER_ID])
        await self.repository.save(manifest)
        response = dict()
        response["uid"] = manifest.uid
        response['wsps health'] = await self.get_health(wsps_uid)
        return response

    @json_response
    async def get_manifest(self, request: Request):
        return await self.repository.load(request.match_info['id'])

    @json_response
    async def delete_manifest(self, request: Request):
        """This method deletes the manifest, as well as workspaces belonging to this manifest, if they are not involved in other manifests.

        """
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
        await self.delete_wsps(wsps_uid, request, None)
        return HTTPNoContent()

    @json_response
    async def change_manifest(self, request: Request):
        """This method makes changes to the manifest.

        If the value of the fields changes:
            - app_uid
            - app_ver
            - model_uid
            - model_ver
        the workspaces are re-created.

        :returns: a list of workspaces health status
        """

        try:
            entity: Manifest = await self.repository.load(request.match_info['id'])
        except Exception as e:
            return HTTPBadRequest(reason=e)

        request_manifest = self._decode_payload(await request.json())

        request_wsps = dict()
        request_wsps_uid = list()
        request_channels = dict()

        manifest_wsps = dict()
        manifest_wsps_uid = list()
        manifest_channels = dict()

        resources = list()
        for r in request_manifest.resources:
            resourse_entity = self.entity_decode_payload(r, Resource)
            resources.append(resourse_entity)
            if resourse_entity.clss == "channel":
                request_channels[resourse_entity.label] = resourse_entity.properties
        request_manifest.resources = resources

        for resourse_entity in resources:
            if resourse_entity.clss == WSP_TYPE_PRODUCER or resourse_entity.clss == WSP_TYPE_WORKSPACE or resourse_entity.clss == WSP_TYPE_CONSUMER:
                wsp: Workspace = self.extract_workspace(resourse_entity, request)
                request_wsps[wsp.uid] = wsp
                request_wsps_uid.append(wsp.uid)

        for resource in entity.resources:
            if resource.clss == "channel":
                manifest_channels[resource.label] = resource.properties

            if resource.clss == WSP_TYPE_PRODUCER or resource.clss == WSP_TYPE_WORKSPACE or resource.clss == WSP_TYPE_CONSUMER:
                wsp: Workspace = self.extract_workspace(resource, request)
                manifest_wsps[wsp.uid] = wsp
                manifest_wsps_uid.append(wsp.uid)

        deleting_uid = list(set(manifest_wsps_uid) - set(request_wsps_uid))
        try:
            await self.delete_wsps(deleting_uid, request, request.match_info['id'])
        except Exception as e:
            return HTTPBadRequest(reason=e)

        creating_uid = list(set(request_wsps_uid) - set(manifest_wsps_uid))
        for wsp_uid in creating_uid:
            await self.wsp_manager.post(request_wsps[wsp_uid])

        changing_uid = list(set(request_wsps_uid) & set(manifest_wsps_uid))
        for wsp_uid in changing_uid:
            if request_wsps[wsp_uid].app_id != manifest_wsps[wsp_uid].app_id or \
                    request_wsps[wsp_uid].app_ver != manifest_wsps[wsp_uid].app_ver or \
                    request_wsps[wsp_uid].model_id != manifest_wsps[wsp_uid].model_id or \
                    request_wsps[wsp_uid].model_ver != manifest_wsps[wsp_uid].model_ver or \
                    request_wsps[wsp_uid].type != manifest_wsps[wsp_uid].type:
                await self.wsp_manager.post(request_wsps[wsp_uid])
            else:
                await self.wsp_manager.save(
                    request_wsps[wsp_uid])

            for resource in request_manifest.resources:
                if resource.clss == WSP_TYPE_PRODUCER or resource.clss == WSP_TYPE_WORKSPACE or resource.clss == WSP_TYPE_CONSUMER:
                    try:
                        route_data = self.extract_route(resource, request_channels)
                        await self.wsp_manager.reroute(workspace=request_wsps.get(resource.properties['uid']),
                                                       route=route_data)
                    except Exception as e:
                        return HTTPBadRequest(reason=e)

        await self.repository.save(request_manifest)

        response = dict()
        response["uid"] = entity.uid
        response['wsps health'] = await self.get_health(request_wsps_uid)
        return response

    def extract_route(self, resource_entity: Resource, channels: dict) -> RouteConfig:
        """Extracting route configuration from Resources

        :resource_entity: Resource
        :channels: dict: dict of Resource.clss == "channel", key - name of entity

        :returns: RouteConfig
        """
        routes = dict()
        routes['pause_stream'] = resource_entity.properties['pause_stream']
        uid = resource_entity.properties['uid']
        if resource_entity.clss == WSP_TYPE_CONSUMER:
            try:
                incoming_key = resource_entity.routes.get("incoming")[0].get('ref')
            except:
                raise Exception(str(resource_entity.label) + " - error routes")
            try:
                routes['incoming_stream'] = channels[incoming_key].get('kafka_topic')
            except:
                raise Exception(incoming_key)
            route_data: RouteConfig = RouteConfigConsumer(wsp_uid=uid, **routes)

        elif resource_entity.clss == WSP_TYPE_PRODUCER:
            try:
                outgoing_key = resource_entity.routes.get("outgoing")[0].get('ref')
            except:
                raise Exception(str(resource_entity.label) + " - error routes")
            try:
                routes['outgoing_stream'] = channels[outgoing_key].get('kafka_topic')
            except:
                raise Exception(outgoing_key)
            route_data: RouteConfig = RouteConfigProducer(wsp_uid=uid, **routes)

        elif resource_entity.clss == WSP_TYPE_WORKSPACE:
            try:
                incoming_key = resource_entity.routes.get("incoming")[0].get('ref')
                outgoing_key = resource_entity.routes.get("outgoing")[0].get('ref')
            except:
                raise Exception(str(resource_entity.label) + " - error routes")
            try:
                routes['incoming_stream'] = channels[incoming_key].get('kafka_topic')
            except:
                raise Exception(incoming_key)
            try:
                routes['outgoing_stream'] = channels[outgoing_key].get('kafka_topic')
            except:
                raise Exception(outgoing_key)
            route_data: RouteConfig = RouteConfigWorkspace(wsp_uid=uid, **routes)
        return route_data

    def entity_decode_payload(self, raw: dict, entity_type):
        """Encoding type from json

        :raw: dict : json body
        :entity_type: type: type of parsing entity

        :return: entity_type
        """
        raw.pop(JSON_TYPE_FIELD, None)
        decoded = proxy_encoder_instance.get_encoder_for_type(entity_type).unpack(raw, entity_type)
        assert isinstance(decoded, entity_type)
        return decoded

    async def delete_wsps(self, wsps_uid: List, request: Request, manifest_uid):
        """Group deletion of workspaces.

        If the workspace belongs to another manifest it will not be deleted

        :wsps_uid: list: list of uids for deleting
        :request: Request
        :manifest_uid: str: uid of the Manifest that the deleted workspaces belong to

        """
        manifests = await self._list(await self._list_query(request))
        busy_wsps_uid = list()
        for manifest in manifests:
            for entity in manifest.resources:
                if entity.clss == WSP_TYPE_PRODUCER or entity.clss == WSP_TYPE_WORKSPACE or entity.clss == WSP_TYPE_CONSUMER:
                    busy_wsps_uid.append(entity.properties['uid'])

        if manifest_uid is not None:
            owner_manifest: Manifest = await self.repository.load(manifest_uid)
            owner_wpsp_uid = list()
            for entity in owner_manifest.resources:
                if entity.clss == WSP_TYPE_PRODUCER or entity.clss == WSP_TYPE_WORKSPACE or entity.clss == WSP_TYPE_CONSUMER:
                    owner_wpsp_uid.append(entity.properties['uid'])
            busy_wsps_uid = list(set(busy_wsps_uid) & set(owner_wpsp_uid))

        for wsp_uid in wsps_uid:
            delete_flag = True
            for busy_uid in busy_wsps_uid:
                if wsp_uid == busy_uid:
                    delete_flag = False
            if delete_flag == True:
                await self.wsp_manager.async_delete(wsp_uid)

    def extract_workspace(self, resourse_entity: Resource, request) -> Workspace:
        """Extract workspace from Resource entity

        """
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
            wsp_entity: Workspace = self.entity_decode_payload(json_wrsp, Workspace)
        except:
            raise Exception("error create workspace")
        return wsp_entity

    async def get_health(self, wsp_uids: list) -> list:
        """Get health status from Consul for list of workspace_uid

        return: list: list of health status for each workspace
        """
        healths = list()
        for wsp_uid in wsp_uids:
            result = dict()
            result['id'] = wsp_uid
            try:
                entity = await self.wsp_manager.get(wsp_uid)
            except:
                result['status'] = "workspace is not exist"
                continue
            health = await self.wsp_manager.health(entity)
            if health[0].get("status") == "not running":
                result['status'] = "creation in progress"
            elif health[0].get("status") != "not running":
                result['status'] = health[0].get("status")
            healths.append(result)
        return healths
