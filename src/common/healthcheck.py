from aiohttp.web_request import Request
from aiohttp.web_response import json_response
from aiohttp.web_urldispatcher import UrlDispatcher

from microcore.base.application import Routable


class HealthCheckAPI(Routable):
    def set_routes(self, router: UrlDispatcher):
        router.add_get('/health', self.handler)

    @staticmethod
    async def handler(_: Request):
        return json_response(
            data={'status': 'ok'},
            status=200
        )
