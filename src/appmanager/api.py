from aiohttp import hdrs
from aiohttp.web import Request
from aiohttp.web_urldispatcher import UrlDispatcher

from common.entities import App
from common.upload import FIELD_FILENAME, accept_upload
from common.versioning import VersionedAPI
from config import SHARED_FS_MOUNT_PATH, SHARED_STORAGE_FILE_PATH_TPL
from container_manager.attachment import AttachmentPrefix
from microcore.entity.encoders import json_response


class ApplicationManagerAPI(VersionedAPI):
    prefix = '/applications'
    entity_type = App

    def set_routes(self, router: UrlDispatcher):
        super().set_routes(router)
        upload = router.add_resource('/{id}/upload')
        upload.add_route(hdrs.METH_POST, self.upload)
        upload.add_prefix(self.prefix)

    @json_response
    async def upload(self, request: Request):
        app: App = await self._get(request)
        meta = await accept_upload(request, path_tpl=SHARED_STORAGE_FILE_PATH_TPL)
        app.attachment = AttachmentPrefix.File.value + meta[FIELD_FILENAME].replace(SHARED_FS_MOUNT_PATH, '')
        await self.repository.save(app)
        return meta
