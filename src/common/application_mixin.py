from common.healthcheck import HealthCheckAPI, HealthCheckService
from microcore.base.application import WebApplication
from microcore.web.api import JsonMiddlewareSet


class CommonAppMixin(WebApplication):
    def _setup(self):
        self.health_check_service = HealthCheckService(
            success_ttl=30,
            failure_ttl=10,
            check_timeout=5,
            loop=self._loop
        )
        self.add_routes_from(
            HealthCheckAPI(service=self.health_check_service)
        )

        self.server.middlewares.append(JsonMiddlewareSet.error)
        self.server.middlewares.append(JsonMiddlewareSet.content_type)

        return super()._setup()
