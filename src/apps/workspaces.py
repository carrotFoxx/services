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
from workspace.adapters import WorkspaceMongoStorageAdapter
from workspace.api import WorkspaceAPI
from workspace.manager import WorkspaceManager


def _injections(binder: inject.Binder):
    app_manager = os.getenv('MGR_APP_DSN', 'ws://app_manager:8080')
    mdl_manager = os.getenv('MGR_MDL_DSN', 'ws://model_manager:8080')
    env_manager = os.getenv('MGR_ENV_DSN', 'ws://env_manager:8080')

    binder.bind_to_constructor(*CRM.provider(
        'rpc_app_manager',
        lambda: RPCClient(server_url=app_manager, encoder=inject.instance(ProxyNativeEncoder)),
        is_async=True
    ))
    binder.bind_to_constructor(*CRM.provider(
        'rpc_model_manager',
        lambda: RPCClient(server_url=mdl_manager, encoder=inject.instance(ProxyNativeEncoder)),
        is_async=True
    ))
    binder.bind_to_constructor(*CRM.provider(
        'rpc_env_manager',
        lambda: RPCClient(server_url=env_manager, encoder=inject.instance(ProxyNativeEncoder)),
        is_async=True
    ))


configure_injector(_injections)


class WorkspaceManagerApp(RPCServerApplication, CommonAppMixin):
    async def _setup(self):
        await super()._setup()

        repository = Repository(WorkspaceMongoStorageAdapter())
        api = WorkspaceAPI(repository=repository, manager=WorkspaceManager(workspaces=repository))
        self.add_routes_from(api)  # add REST endpoints
        self.add_methods_from(api)  # add RPC endpoints

        self.cors_add_all()
        self.health_check_service.add_check(health_checkers.mongo_available)
        self.health_check_service.add_check(health_checkers.consul_available)
        self.health_check_service.add_check(health_checkers.rpc_app_manager_alive)
        self.health_check_service.add_check(health_checkers.rpc_mdl_manager_alive)
        self.health_check_service.add_check(health_checkers.rpc_env_manager_alive)
        self.server.middlewares.append(OwnedMiddlewareSet.extract_owner)

    async def _shutdown(self):
        await super()._shutdown()
        await CRM.close_all(loop=self._loop)


if __name__ == '__main__':
    ROOT_LOG.info('starting [%s]', WorkspaceManagerApp.__name__)
    WorkspaceManagerApp().run()
