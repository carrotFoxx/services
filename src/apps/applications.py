from appmanager.adapters import AppMongoStorageAdapter
from appmanager.api import ApplicationManagerAPI
from injector import configure_injector
from microcore.base.application import WebApplication
from microcore.base.repository import Repository

configure_injector()


class ApplicationManagerApp(WebApplication):
    async def _setup(self):
        await super()._setup()

        self.add_routes_from(
            ApplicationManagerAPI(
                repository=Repository(AppMongoStorageAdapter())
            )
        )


if __name__ == '__main__':
    ApplicationManagerApp().run()
