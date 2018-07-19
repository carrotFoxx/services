import logging
from typing import Union

from aiohttp.web_exceptions import HTTPForbidden
from aiohttp.web_request import Request

from microcore.entity.abstract import Identifiable, Owned
from .api import ReadOnlyStorageAPI, ReadWriteStorageAPI

logger = logging.getLogger(__name__)

HEADER_USER_ID = 'x-user-id'
OWNER_ID = 'owner_id'
OWNER_PROP = 'owner'


class OwnedReadOnlyStorageAPI(ReadOnlyStorageAPI):
    async def _get(self, request: Request):
        entity: Owned = await self.repository.load(request.match_info['id'])
        if entity.get_owner() != request[OWNER_ID]:
            raise HTTPForbidden()
        return entity

    async def _list_query(self, request: Request) -> dict:
        properties = await super()._list_query(request)
        properties[OWNER_PROP] = request[OWNER_ID]
        return properties


class OwnedReadWriteStorageAPI(OwnedReadOnlyStorageAPI, ReadWriteStorageAPI):
    async def _post_transformer(self, request: Request):
        entity: Owned = self._decode_payload(await request.json())
        entity.set_owner(request[OWNER_ID])
        return entity

    async def _put_transformer(self, request: Request):
        entity: Union[Identifiable, Owned] = self._decode_payload(await request.json())
        entity.set_owner(request[OWNER_ID])
        entity.set_uid(request.match_info['id'])
        return entity


class OwnedMiddlewareSet:
    @staticmethod
    async def extract_owner(app, handler):
        async def extract_owner_handler(request: Request):
            if request.headers.get(HEADER_USER_ID):
                request[OWNER_ID] = request.headers[HEADER_USER_ID]
                logger.debug('detected user [%s]' % request[OWNER_ID])
            else:
                logger.warning('no x-user-id header detected')
            return await handler(request)

        return extract_owner_handler
