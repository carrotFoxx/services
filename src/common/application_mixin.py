from common import health_checkers
from common.healthcheck import HealthCheckAPI, HealthCheckService
from config import SENTRY_DSN
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
        return super()._setup()
