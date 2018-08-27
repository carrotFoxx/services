import os

from common.consul import ConsulClient
from config import ROOT_LOG
from microcore.base.application import Application
from supervisor.manager import Supervisor
from supervisor.state import StateMonitor


class SupervisorApp(Application):

    async def _setup(self):
        await super()._setup()
        self.manager = Supervisor(
            state_monitor=StateMonitor(
                node_id=os.environ.get('BDZ_NODE_ID'),
                consul=ConsulClient(
                    base='http://consul:8500/v1/',
                    loop=self._loop
                ),
                loop=self._loop
            )
        )
        await self.manager.start()

    async def _shutdown(self):
        await self.manager.stop()
        await super()._shutdown()


if __name__ == '__main__':
    ROOT_LOG.info('starting...')
    SupervisorApp().run()
