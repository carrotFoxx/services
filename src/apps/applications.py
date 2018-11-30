from appmanager.adapters import AppArchiveMongoStorageAdapter, AppMongoStorageAdapter
from appmanager.api import ApplicationManagerAPI
from common import health_checkers
from common.application_mixin import CommonAppMixin
from common.versioning import VersionedRPCAPI
from config import ROOT_LOG
from injector import configure_injector
from mco.rpc import RPCServerApplication
from microcore.base.repository import Repository
from microcore.web.owned_api import OwnedMiddlewareSet

configure_injector()


class ApplicationManagerApp(RPCServerApplication, CommonAppMixin):
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
        self.cors_add_all()
        self.health_check_service.add_check(health_checkers.mongo_available)
        self.server.middlewares.append(OwnedMiddlewareSet.extract_owner)


if __name__ == '__main__':
    ROOT_LOG.info('starting [%s]', ApplicationManagerApp.__name__)
    ApplicationManagerApp().run()
