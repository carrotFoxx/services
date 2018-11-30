from typing import Dict, cast

import aiohttp_cors
from aiohttp.web_urldispatcher import UrlDispatcher

from common import health_checkers
from common.healthcheck import HealthCheckAPI, HealthCheckService
from config import ROOT_LOG, SENTRY_DSN
from microcore.base.application import WebApplication
from microcore.web.api import JsonMiddlewareSet


class CommonAppMixin(WebApplication):
    def _setup(self):
        self.health_check_service = HealthCheckService(
            check_timeout=5,
            loop=self._loop
        )
        self.add_routes_from(
            HealthCheckAPI(service=self.health_check_service)
        )

        self.server.middlewares.append(JsonMiddlewareSet.error)
        self.server.middlewares.append(JsonMiddlewareSet.content_type)
        if SENTRY_DSN is not None:
            self.health_check_service.add_check(health_checkers.sentry_reachable)

        self.cors = aiohttp_cors.setup(self.server, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*"
            )
        })
        return super()._setup()

    def cors_add_all(self, rules: Dict[str, aiohttp_cors.ResourceOptions] = None):
        for route in list(cast(UrlDispatcher, self.server.router).routes()):
            ROOT_LOG.debug('add CORS for route %s', route)
            try:
                self.cors.add(route, rules)
            except ValueError:
                ROOT_LOG.warning('failed to add CORS for route %s', route, exc_info=True)
