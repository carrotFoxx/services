from config import ROOT_LOG
from container_manager.api import ContainerManagerRPCAPI
from container_manager.docker import DockerProvider
from container_manager.manager import ContainerManager
from injector import configure_injector
from mco.rpc import RPCServerApplication

configure_injector()


class EnvironmentManagerApp(RPCServerApplication):
    async def _setup(self):
        await super()._setup()
        self.controller = ContainerManagerRPCAPI(
            ContainerManager(DockerProvider())
        )
        self.controller.set_routes(self.rpc_setup)


if __name__ == '__main__':
    ROOT_LOG.info('starting [%s]', EnvironmentManagerApp.__name__)
    EnvironmentManagerApp().run()
