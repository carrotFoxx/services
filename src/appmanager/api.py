from aiohttp import hdrs
from aiohttp.web_urldispatcher import UrlDispatcher

from common.entities import App
from microcore.base.application import Routable
from microcore.web.api import ReadWriteStorageAPI


class ApplicationManagerAPI(Routable, ReadWriteStorageAPI):
    entity_type = App

    def set_routes(self, router: UrlDispatcher):
        app_root = router.add_resource('/applications/')
        app_root.add_route(hdrs.METH_GET, self.list)
        app_root.add_route(hdrs.METH_POST, self.post)

        app_inst = router.add_resource('/applications/{id}')
        app_inst.add_route(hdrs.METH_GET, self.get)
        app_inst.add_route(hdrs.METH_PUT, self.put)
        app_inst.add_route(hdrs.METH_DELETE, self.delete)
