from common import health_checkers
from common.application_mixin import CommonAppMixin
from common.versioning import VersionedRPCAPI
from config import ROOT_LOG
from injector import configure_injector
from mco.rpc import RPCServerApplication
from microcore.base.repository import Repository
from microcore.web.owned_api import OwnedMiddlewareSet
from modelmanager.adapters import ModelArchiveMongoStorageAdapter, ModelMongoStorageAdapter
from modelmanager.api import ModelManagerAPI

configure_injector()


class ModelManagerApp(RPCServerApplication, CommonAppMixin):
    async def _setup(self):
        await super()._setup()

        repository = Repository(ModelMongoStorageAdapter())
        archive = Repository(ModelArchiveMongoStorageAdapter())
        self.add_routes_from(
            ModelManagerAPI(
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
        self.health_check_service.add_check(health_checkers.mongo_available)
        self.server.middlewares.append(OwnedMiddlewareSet.extract_owner)


if __name__ == '__main__':
    ROOT_LOG.info('starting [%s]', ModelManagerApp.__name__)
    ModelManagerApp().run()
