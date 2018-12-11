import os

import inject

from common import health_checkers
from common.application_mixin import CommonAppMixin
from config import MONGO_DB, ROOT_LOG
from injector import CRM, configure_injector
from mco.rpc import RPCClient, RPCServerApplication
from microcore.entity.encoders import ProxyNativeEncoder
from microcore.storage.mongo import motor
from microcore.web.owned_api import OwnedMiddlewareSet
from results_manager.api import ResultsManagerAPI


def _injections(binder: inject.Binder):
    wsp_manager = os.getenv('MGR_WSP_DSN', 'ws://wsp_manager:8080')

    binder.bind_to_constructor(*CRM.provider(
        'rpc_wsp_manager',
        lambda: RPCClient(server_url=wsp_manager, encoder=inject.instance(ProxyNativeEncoder)),
        is_async=True
    ))


configure_injector(_injections)


class ResultsManagerApp(RPCServerApplication, CommonAppMixin):
    async def _setup(self):
        await super()._setup()

        self.add_routes_from(ResultsManagerAPI(
            results_db=MONGO_DB,
            events_db=motor().events
        ))

        self.cors_add_all()
        self.health_check_service.add_check(health_checkers.mongo_available)
        self.health_check_service.add_check(health_checkers.consul_available)
        self.health_check_service.add_check(health_checkers.rpc_wsp_manager_alive)
        self.server.middlewares.append(OwnedMiddlewareSet.extract_owner)

    async def _shutdown(self):
        await super()._shutdown()
        await CRM.close_all(loop=self._loop)


if __name__ == '__main__':
    ROOT_LOG.info('starting [%s]', ResultsManagerApp.__name__)
    ResultsManagerApp().run()
