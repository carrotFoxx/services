from aiohttp import hdrs
from aiohttp.web import Request
from aiohttp.web_urldispatcher import UrlDispatcher

from common.entities import App, Model
from common.upload import FIELD_FILENAME, accept_upload
from common.versioning import VersionedAPI
from microcore.entity.encoders import json_response


class ModelManagerAPI(VersionedAPI):
    prefix = '/models'
    entity_type = App

    def set_routes(self, router: UrlDispatcher):
        super().set_routes(router)
        upload = router.add_resource('/{id}/upload')
        upload.add_route(hdrs.METH_POST, self.upload)
        upload.add_prefix(self.prefix)

    @json_response
    async def upload(self, request: Request):
        model: Model = await self._get(request)
        meta = await accept_upload(request)
        model.attachment = meta[FIELD_FILENAME]
        await self.repository.save(model)
        return meta
