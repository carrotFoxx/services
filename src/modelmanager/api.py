from aiohttp import hdrs
from aiohttp.web import Request
from aiohttp.web_urldispatcher import UrlDispatcher

from common.download import accept_download
from common.entities import Model
from common.upload import FIELD_FILENAME, accept_upload
from common.versioning import VersionedAPI
from config import SHARED_FS_MOUNT_PATH, SHARED_STORAGE_FILE_PATH_TPL
from container_manager.attachment import AttachmentPrefix
from microcore.entity.encoders import json_response


class ModelManagerAPI(VersionedAPI):
    prefix = '/models'
    entity_type = Model

    def set_routes(self, router: UrlDispatcher):
        super().set_routes(router)
        upload = router.add_resource('/{id}/upload')
        upload.add_route(hdrs.METH_POST, self.upload)
        upload.add_prefix(self.prefix)
        download = router.add_resource('/{id}/versions/{vid}/download')
        download.add_route(hdrs.METH_GET, self.download)
        download.add_prefix(self.prefix)

    @json_response
    async def upload(self, request: Request):
        model: Model = await self._get(request)
        meta = await accept_upload(request, path_tpl=SHARED_STORAGE_FILE_PATH_TPL)
        model.attachment = AttachmentPrefix.File.value + meta[FIELD_FILENAME].replace(SHARED_FS_MOUNT_PATH, '')
        await self.repository.save(model)
        return meta

    async def download(self, request: Request):
        model: Model = await self.archive.find_one(uid=request.match_info['id'],
                                                 version=int(request.match_info['vid']))
        meta = await accept_download(request, SHARED_FS_MOUNT_PATH +
                                     model.attachment.replace(AttachmentPrefix.File.value, ""),
                                     path_tpl=SHARED_STORAGE_FILE_PATH_TPL)
        return meta
