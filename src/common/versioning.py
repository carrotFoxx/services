import asyncio
import json
import logging
from typing import List, Type, Union

import attr
from aiohttp import hdrs
from aiohttp.web import HTTPBadRequest, HTTPInternalServerError, HTTPNotFound, HTTPPreconditionFailed, \
    HTTPPreconditionRequired, Request, Response
from aiohttp.web_urldispatcher import UrlDispatcher
from aiohttp_json_rpc import RpcGenericServerDefinedError, RpcInvalidParamsError

from mco.entities import ObjectBase, OwnedObject
from mco.rpc import RPCRoutable, rpc_expose
from microcore.base.application import Routable
from microcore.base.repository import DoesNotExist, Repository, StorageException, VersionMismatch
from microcore.entity.abstract import Preserver
from microcore.entity.encoders import ProxyJSONEncoder, json_response
from microcore.web.owned_api import OwnedReadWriteStorageAPI

logger = logging.getLogger(__name__)


@attr.s(auto_attribs=True)
class VersionedObject(ObjectBase, OwnedObject, Preserver):
    version: int = 0

    def preserve_from(self, other: 'VersionedObject'):
        super().preserve_from(other)
        self.uid = other.uid
        self.owner = other.owner
        self.version = other.version


E_TAG = 'X-Version'
IF_MATCH = 'X-If-Version'


def ensure_has_header(header: str):
    def decorator(fn):
        def ensure_header(self, request: Request):
            if request.headers.get(header) is None:
                raise HTTPPreconditionRequired(reason=f'{header} header must be set')
            return fn(self, request)

        return ensure_header

    return decorator


class VersionedAPI(OwnedReadWriteStorageAPI, Routable):
    prefix = None
    entity_type: Type[VersionedObject] = VersionedObject

    def __init__(self, repository: Repository, archive: Repository):
        super().__init__(repository)
        self.archive: Repository = archive

    def set_routes(self, router: UrlDispatcher):
        resources = []

        root = router.add_resource('')
        root.add_route(hdrs.METH_GET, self.list)
        root.add_route(hdrs.METH_POST, self.post)
        resources.append(root)

        item = router.add_resource('/{id}')
        item.add_route(hdrs.METH_GET, self.get)
        item.add_route(hdrs.METH_PUT, self.put)
        item.add_route(hdrs.METH_DELETE, self.delete)
        resources.append(item)

        versions_root = router.add_resource('/{id}/versions')
        versions_root.add_route(hdrs.METH_GET, self.list_versions)
        resources.append(versions_root)

        versions_item = router.add_resource('/{id}/versions/{vid}')
        versions_item.add_route(hdrs.METH_GET, self.get_version)
        resources.append(versions_item)

        commit = router.add_resource('/{id}/commit')
        commit.add_route(hdrs.METH_POST, self.commit_version)
        resources.append(commit)

        if self.prefix:
            for r in resources:
                r.add_prefix(self.prefix)

        logger.debug('registered resources: %s',
                     [r.canonical for r in router.resources()])

    async def get(self, request: Request):
        try:
            entity: VersionedObject = await self._get(request)
        except DoesNotExist:
            raise HTTPNotFound()
        return Response(headers={E_TAG: str(entity.version)},
                        text=json.dumps(entity, cls=ProxyJSONEncoder))

    async def post(self, request: Request):
        entity: VersionedObject = await self._catch_input(request, self._post_transformer)
        try:
            await self._post(entity)
        except StorageException as e:
            raise HTTPInternalServerError() from e
        return Response(status=201, headers={E_TAG: str(entity.version)},
                        text=json.dumps(entity, cls=ProxyJSONEncoder))

    async def _put_transformer(self, request: Request):
        entity: VersionedObject = await super()._put_transformer(request)
        entity.version = int(request.headers[IF_MATCH])
        return entity

    @json_response
    async def _put(self, new: entity_type, existing: Union[entity_type, None] = None):
        if existing is not None:
            new.preserve_from(existing)
        await super()._put(new, existing)
        return new

    @ensure_has_header(IF_MATCH)
    async def put(self, request: Request):
        entity: VersionedObject = await self._catch_input(request, self._put_transformer)

        try:
            stored: VersionedObject = await self._get(request)
            if stored.version != int(request.headers[IF_MATCH]):
                raise HTTPPreconditionFailed(reason='Version mismatch')
        except DoesNotExist:
            stored = None
            pass  # just create with defined id if not exists

        try:
            response: Response = await self._put(new=entity, existing=stored)
            response.headers[E_TAG] = str(entity.version)
            return response
        except VersionMismatch as e:
            raise HTTPPreconditionFailed(reason='Version mismatch') from e
        except StorageException as e:
            raise HTTPInternalServerError() from e

    @ensure_has_header(IF_MATCH)
    async def delete(self, request: Request):
        try:
            entity: VersionedObject = await self._get(request)
            if entity.version != int(request.headers.get(IF_MATCH)):
                raise HTTPPreconditionFailed(reason='Version mismatch')
            await self._delete(entity)
        except DoesNotExist:
            raise HTTPNotFound()
        except StorageException as e:
            raise HTTPInternalServerError() from e
        return Response(status=204)

    @json_response
    async def get_version(self, request: Request):
        try:
            entity = await self.archive.find_one(uid=request.match_info['id'],
                                                 version=int(request.match_info['vid']))
        except DoesNotExist:
            raise HTTPNotFound
        return entity

    @json_response
    async def list_versions(self, request: Request):
        try:
            query = await self._list_query(request)
            lst = await self.archive.find({**query, 'uid': request.match_info['id']})
        except AttributeError as e:
            raise HTTPBadRequest from e
        return lst

    @ensure_has_header(IF_MATCH)
    @json_response
    async def commit_version(self, request: Request):
        try:
            entity: VersionedObject = await self._get(request)
            if entity.version != int(request.headers.get(IF_MATCH)):
                raise HTTPPreconditionFailed(reason='Version mismatch')
        except DoesNotExist:
            raise HTTPNotFound
        # wrap with shield
        entity = await asyncio.shield(self._commit_version_write(entity))
        return {'version': entity.version}

    async def _commit_version_write(self, entity: VersionedObject):
        try:
            latest: VersionedObject = await self.archive.find_one(**{
                'uid': entity.uid,
                '_sort': {'version': -1}
            })
            top_version = latest.version
        except DoesNotExist:
            top_version = 0

        entity.version = top_version + 1
        await self.archive.save(entity)
        await self.repository.save(entity)
        return entity


class VersionedRPCAPI(RPCRoutable):
    entity_type: Type[VersionedObject] = VersionedObject

    def __init__(self, repository: Repository, archive: Repository) -> None:
        super().__init__()
        self.repository: Repository = repository
        self.archive: Repository = archive

    def set_methods(self) -> List[callable]:
        return [
            rpc_expose(self.repository.load, name='get'),
            rpc_expose(self.repository.save, name='create'),
            self.update,
            rpc_expose(self.repository.delete, name='delete'),
            rpc_expose(self.repository.find, name='list'),
            self.list_versions,
            self.get_version
        ]

    async def update(self, obj: VersionedObject) -> VersionedObject:
        existing: VersionedObject = await self.repository.load(obj.uid)
        obj.preserve_from(existing)
        await self.repository.save(existing)
        return existing

    async def list_versions(self, uid: str, query: dict = None) -> List[VersionedObject]:
        try:
            lst = await self.archive.find({**query, 'uid': uid})
        except AttributeError as e:
            raise RpcInvalidParamsError(message=str(e)) from e
        return lst

    async def get_version(self, uid: str, version: int) -> VersionedObject:
        try:
            entity = await self.archive.find_one(uid=uid, version=int(version))
        except DoesNotExist:
            raise RpcGenericServerDefinedError(error_code=-32044, message='not found')
        return entity
