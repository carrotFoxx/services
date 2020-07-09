import os

import inject

from common import health_checkers
from common.application_mixin import CommonAppMixin
from config import ROOT_LOG
from injector import CRM, configure_injector
from mco.rpc import RPCClient, RPCServerApplication
from microcore.base.repository import Repository
from microcore.entity.encoders import ProxyNativeEncoder
from microcore.web.owned_api import OwnedMiddlewareSet
from script.adapters import ChainMongoStorageAdapter
from script.api import ScriptAPI



def _injections(binder: inject.Binder):

    wsp_manager = os.getenv('MGR_ENV_DSN', 'ws://wsp_manager:8080')


    binder.bind_to_constructor(*CRM.provider(
        'rpc_wsp_manager',
        lambda: RPCClient(server_url=wsp_manager, encoder=inject.instance(ProxyNativeEncoder)),
        is_async=True
    ))


configure_injector(_injections)


class ScriptManagerApp(RPCServerApplication, CommonAppMixin):
    async def _setup(self):
        await super()._setup()

        repository = Repository(ChainMongoStorageAdapter())

        api = ScriptAPI(repository=repository)
        self.add_routes_from(api)  # add REST endpoints
        self.add_methods_from(api)  # add RPC endpoints

        self.cors_add_all()
        self.health_check_service.add_check(health_checkers.mongo_available)
        self.health_check_service.add_check(health_checkers.consul_available)
        self.health_check_service.add_check(health_checkers.rpc_wsp_manager_alive)
        self.server.middlewares.append(OwnedMiddlewareSet.extract_owner)

    async def _shutdown(self):
        await super()._shutdown()
        await CRM.close_all(loop=self._loop)


if __name__ == '__main__':
    ROOT_LOG.info('starting [%s]', ScriptManagerApp.__name__)
    ScriptManagerApp().run()
