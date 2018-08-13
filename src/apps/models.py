from config import ROOT_LOG
from injector import configure_injector
from microcore.base.application import WebApplication
from microcore.base.repository import Repository
from microcore.web.api import JsonMiddlewareSet
from microcore.web.owned_api import OwnedMiddlewareSet
from modelmanager.adapters import ModelArchiveMongoStorageAdapter, ModelMongoStorageAdapter
from modelmanager.api import ModelManagerAPI

configure_injector()


class ModelManagerApp(WebApplication):
    async def _setup(self):
        await super()._setup()

        self.add_routes_from(
            ModelManagerAPI(
                repository=Repository(ModelMongoStorageAdapter()),
                archive=Repository(ModelArchiveMongoStorageAdapter())
            )
        )

        self.server.middlewares.append(JsonMiddlewareSet.error)
        self.server.middlewares.append(JsonMiddlewareSet.content_type)
        self.server.middlewares.append(OwnedMiddlewareSet.extract_owner)


if __name__ == '__main__':
    ROOT_LOG.info('starting [%s]', ModelManagerApp.__name__)
    ModelManagerApp().run()
