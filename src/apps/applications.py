from appmanager.adapters import AppArchiveMongoStorageAdapter, AppMongoStorageAdapter
from appmanager.api import ApplicationManagerAPI
from config import ROOT_LOG
from injector import configure_injector
from microcore.base.application import WebApplication
from microcore.base.repository import Repository
from microcore.web.api import JsonMiddlewareSet
from microcore.web.owned_api import OwnedMiddlewareSet

configure_injector()


class ApplicationManagerApp(WebApplication):
    async def _setup(self):
        await super()._setup()

        self.add_routes_from(
            ApplicationManagerAPI(
                repository=Repository(AppMongoStorageAdapter()),
                archive=Repository(AppArchiveMongoStorageAdapter())
            )
        )

        self.server.middlewares.append(JsonMiddlewareSet.error)
        self.server.middlewares.append(JsonMiddlewareSet.content_type)
        self.server.middlewares.append(OwnedMiddlewareSet.extract_owner)


if __name__ == '__main__':
    ROOT_LOG.info('starting [%s]', ApplicationManagerApp.__name__)
    ApplicationManagerApp().run()
