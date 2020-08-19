import logging
from typing import List, Dict

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
        root.add_route(hdrs.METH_POST, self.post_manifest)

        hlth = router.add_resource('/scripts/health/{id}')
        hlth.add_route(hdrs.METH_GET, self.get_status)

        item = router.add_resource('/scripts/{id}')
        item.add_route(hdrs.METH_GET, self.get_manifest)
        item.add_route(hdrs.METH_DELETE, self.delete_manifest)
        item.add_route(hdrs.METH_PUT, self.change_manifest)

    def set_methods(self) -> List[callable]:
        return [
        ]

    @json_response
    async def post_manifest(self, request: Request):

        manifest: Manifest = await self.decode_payload_manifest(request)
        try:
            await self.repository.load(manifest.uid)
            return HTTPBadRequest(reason="entity exist")
        except:
            pass
        wsps, wsps_uid, routes = self.extract_workspaces(manifest.resources, request)
        for uid in wsps_uid:
            try:
                await self.wsp_manager.post(wsps[uid])
            except Exception as e:
                await self.delete_wsps(wsps_uid, request, None)
                return HTTPBadRequest(reason=e)
            try:
                await self.wsp_manager.reroute(workspace=wsps[uid], route=routes[uid])
            except Exception as e:
                await self.delete_wsps(wsps_uid, request, None)
                return HTTPBadRequest(reason="invalid link: " + str(e))

        manifest.set_owner(request[OWNER_ID])
        await self.repository.save(manifest)
        return await self.make_status_response(manifest.uid, wsps_uid)

    @json_response
    async def get_manifest(self, request: Request):
        return await self.repository.load(request.match_info['id'])

    @json_response
    async def delete_manifest(self, request: Request):
        """This method deletes the manifest, as well as workspaces belonging to this manifest, if they are not involved in other manifests.

        """
        try:
            manifest: Manifest = await self.repository.load(request.match_info['id'])
        except DoesNotExist:
            return HTTPNotFound()
        wsps_uid = self.extract_workspaces(manifest.resources, request)[1]
        await self.repository.delete(request.match_info['id'])
        await self.delete_wsps(wsps_uid, request, None)
        return HTTPNoContent()

    @json_response
    async def change_manifest(self, request: Request):
        """makes changes to the manifest.

        If the value of the fields changes:
            - app_uid
            - app_ver
            - model_uid
            - model_ver
        the workspaces are re-created.

        :returns: a list of workspaces health status
        """

        try:
            local_manifest: Manifest = await self.repository.load(request.match_info['id'])
        except Exception as e:
            return HTTPBadRequest(reason=e)

        request_manifest = await self.decode_payload_manifest(request)
        request_wsps, request_wsps_uid, request_routes = self.extract_workspaces(request_manifest.resources,request)
        manifest_wsps, manifest_wsps_uid, manifest_routes = self.extract_workspaces(local_manifest.resources,request) # переименовать

        deleting_uid = list(set(manifest_wsps_uid) - set(request_wsps_uid))
        try:
            await self.delete_wsps(deleting_uid, request, request.match_info['id'])
        except Exception as e:
            pass

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
                try:
                    wsp = await self.wsp_manager.get(wsp_uid)
                    request_wsps[wsp_uid].created = wsp.created
                except:
                    pass
                await self.wsp_manager.save(request_wsps[wsp_uid])

        for uid in request_wsps_uid:
            try:
                await self.wsp_manager.reroute(workspace=request_wsps[uid], route=request_routes[uid])
            except Exception as e:
                return HTTPBadRequest(reason="invalid link: " + str(e))
        request_manifest.set_owner(request[OWNER_ID])
        await self.repository.save(request_manifest)
        return await self.make_status_response(local_manifest.uid, request_wsps_uid)

    @json_response
    async def get_status(self, request: Request):
        """returns the health status for each workspace contained in the manifest.

        :returns: a list of workspaces health status
        """

        try:
            entity: Manifest = await self.repository.load(request.match_info['id'])
        except Exception as e:
            return HTTPBadRequest(reason=e)

        response = dict()
        response["uid"] = entity.uid
        response["wsps health"] = await self.get_health(self.extract_workspaces(entity.resources, request)[1])
        return response

    def extract_routes(self, resources: Manifest.resources, channels: dict):
        routes = dict()
        for resource in resources:
            if resource.class_ == WSP_TYPE_PRODUCER or resource.class_ == WSP_TYPE_WORKSPACE or resource.class_ == WSP_TYPE_CONSUMER:
                try:
                    routes[resource.uid] = self.extract_route(resource, channels)
                except Exception as e:
                    return HTTPBadRequest(reason=e)
        return routes

    def extract_route(self, resource_entity: Resource, channels: dict) -> RouteConfig:
        """Extracting route configuration from Resource entities

        :resource_entity: Resource
        :channels: dict: dict of Resource.class_ == "channel", key - name of entity

        :returns: RouteConfig
        """
        routes = dict()
        routes['pause_stream'] = resource_entity.properties['pause_stream']
        uid = resource_entity.uid
        if resource_entity.class_ == WSP_TYPE_CONSUMER:
            try:
                incoming_key = resource_entity.routes.get("incoming")[0].get('ref')
            except:
                raise Exception(str(resource_entity.label) + " - error routes")
            try:
                routes['incoming_stream'] = channels[incoming_key].get('kafka_topic')
            except:
                raise Exception(incoming_key)
            route_data: RouteConfig = RouteConfigConsumer(wsp_uid=uid, **routes)

        elif resource_entity.class_ == WSP_TYPE_PRODUCER:
            try:
                outgoing_key = resource_entity.routes.get("outgoing")[0].get('ref')
            except:
                raise Exception(str(resource_entity.label) + " - error routes")
            try:
                routes['outgoing_stream'] = channels[outgoing_key].get('kafka_topic')
            except:
                raise Exception(outgoing_key)
            route_data: RouteConfig = RouteConfigProducer(wsp_uid=uid, **routes)

        elif resource_entity.class_ == WSP_TYPE_WORKSPACE:
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
                if entity.class_ == WSP_TYPE_PRODUCER or entity.class_ == WSP_TYPE_WORKSPACE or entity.class_ == WSP_TYPE_CONSUMER:
                    busy_wsps_uid.append(entity.uid)

        if manifest_uid is not None:
            owner_manifest: Manifest = await self.repository.load(manifest_uid)
            owner_wpsp_uid = list()
            for entity in owner_manifest.resources:
                if entity.class_ == WSP_TYPE_PRODUCER or entity.class_ == WSP_TYPE_WORKSPACE or entity.class_ == WSP_TYPE_CONSUMER:
                    owner_wpsp_uid.append(entity.uid)
            busy_wsps_uid = list(set(busy_wsps_uid) - set(owner_wpsp_uid))

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
            if resourse_entity.uid != None and resourse_entity.uid != '':
                json_wrsp['uid'] = resourse_entity.uid
            if resourse_entity.properties.get('name') == '':
                raise
            else:
                json_wrsp['name'] = resourse_entity.properties.get('name')
            json_wrsp['type'] = resourse_entity.properties.get('class_')
            json_wrsp['app_id'] = resourse_entity.properties.get('application').get('id')
            json_wrsp['app_ver'] = resourse_entity.properties.get('application').get('version')
            json_wrsp['model_id'] = resourse_entity.properties.get('model').get('id')
            json_wrsp['model_ver'] = resourse_entity.properties.get('model').get('version')
            json_wrsp['owner'] = request["owner_id"]
            json_wrsp['type'] = resourse_entity.class_
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
                healths.append(result)
                continue
            health = await self.wsp_manager.health(entity)
            if health[0].get("status") == "not running":
                result['status'] = "creation in progress"
            elif health[0].get("status") != "not running":
                result['status'] = health[0].get("status")
            healths.append(result)
        return healths

    def extract_workspaces(self, resources: list, request: Request):
        """Extract workspace entity from Manifest.resources

        return: Dict[uid, Workspace], List[uid]
        """
        wsps: Dict[str, Workspace] = dict()
        wsps_uid: List[str] = list()
        wsps_routes = dict()#: Dict[uid, Rout]
        channels = self.extract_channels(resources)
        for resource_entity in resources:
            if resource_entity.class_ == WSP_TYPE_PRODUCER or resource_entity.class_ == WSP_TYPE_WORKSPACE or resource_entity.class_ == WSP_TYPE_CONSUMER:
                wsp: Workspace = self.extract_workspace(resource_entity, request)
                wsps[wsp.uid] = wsp
                wsps_routes[wsp.uid] = self.extract_route(resource_entity,channels)
                wsps_uid.append(wsp.uid)
                resource_entity.uid = wsp.uid
        return wsps, wsps_uid, wsps_routes

    def extract_channels(self, resources: list):
        """Extract channels entity from Manifest.resources

        resources: Manifest.resources
        return: Dict[label, properties]
        """
        request_channels = dict()
        for resourse_entity in resources:
            if resourse_entity.class_ == "channel":
                request_channels[resourse_entity.label] = resourse_entity.properties
        return request_channels

    async def decode_payload_manifest(self, request: Request):
        """ decode payload for Manifest entity

        return: Manifest
        """
        manifest = self._decode_payload(await request.json())
        resources = list()
        for r in manifest.resources:
            resourse_entity = self.entity_decode_payload(r, Resource)
            resources.append(resourse_entity)
        manifest.resources = resources
        return manifest

    async def make_status_response(self, uid, wsps_uid):
        response = dict()
        response["uid"] = uid
        response['wsps health'] = await self.get_health(wsps_uid)
        return response
