import inject

from common.healthcheck import HealthCheckAPI
from config import ROOT_LOG
from injector import async_close_registered, closable, configure_injector
from mco.rpc import RPCClient, RPCServerApplication
from microcore.base.repository import Repository
from microcore.entity.encoders import ProxyNativeEncoder
from microcore.web.api import JsonMiddlewareSet
from microcore.web.owned_api import OwnedMiddlewareSet
from workspace.adapters import WorkspaceMongoStorageAdapter
from workspace.api import WorkspaceAPI
from workspace.manager import WorkspaceManager


def _injections(binder: inject.Binder):
    binder.bind_to_constructor(
        closable('rpc_app_manager'),
        lambda: RPCClient(server_url='ws://app_manager:8080',
                          encoder=inject.instance(ProxyNativeEncoder)))
    binder.bind_to_constructor(
        closable('rpc_model_manager'),
        lambda: RPCClient(server_url='ws://model_manager:8080',
                          encoder=inject.instance(ProxyNativeEncoder)))
    binder.bind_to_constructor(
        closable('rpc_env_manager'),
        lambda: RPCClient(server_url='ws://env_manager:8080',
                          encoder=inject.instance(ProxyNativeEncoder)))


configure_injector(_injections)


class WorkspaceManagerApp(RPCServerApplication):
    async def _setup(self):
        await super()._setup()

        repository = Repository(WorkspaceMongoStorageAdapter())
        self.add_routes_from(
            WorkspaceAPI(
                repository=repository,
                manager=WorkspaceManager(workspaces=repository)
            )
        )
        self.add_routes_from(
            HealthCheckAPI()
        )

        self.server.middlewares.append(JsonMiddlewareSet.error)
        self.server.middlewares.append(JsonMiddlewareSet.content_type)
        self.server.middlewares.append(OwnedMiddlewareSet.extract_owner)

    async def _shutdown(self):
        await super()._shutdown()
        await async_close_registered(lambda x: x.close())


if __name__ == '__main__':
    ROOT_LOG.info('starting [%s]', WorkspaceManagerApp.__name__)
    WorkspaceManagerApp().run()
