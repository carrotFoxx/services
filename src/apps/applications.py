from appmanager.adapters import AppArchiveMongoStorageAdapter, AppMongoStorageAdapter
from appmanager.api import ApplicationManagerAPI
from common.versioning import VersionedRPCAPI
from config import ROOT_LOG
from injector import configure_injector
from mco.rpc import RPCServerApplication
from microcore.base.repository import Repository
from microcore.web.api import JsonMiddlewareSet
from microcore.web.owned_api import OwnedMiddlewareSet

configure_injector()


class ApplicationManagerApp(RPCServerApplication):
    async def _setup(self):
        await super()._setup()

        repository = Repository(AppMongoStorageAdapter())
        archive = Repository(AppArchiveMongoStorageAdapter())
        self.add_routes_from(
            ApplicationManagerAPI(
                repository=repository,
                archive=archive
            )
        )
        self.add_methods_from(
            VersionedRPCAPI(
                repository=repository,
                archive=archive
            )
        )

        self.server.middlewares.append(JsonMiddlewareSet.error)
        self.server.middlewares.append(JsonMiddlewareSet.content_type)
        self.server.middlewares.append(OwnedMiddlewareSet.extract_owner)


if __name__ == '__main__':
    ROOT_LOG.info('starting [%s]', ApplicationManagerApp.__name__)
    ApplicationManagerApp().run()
