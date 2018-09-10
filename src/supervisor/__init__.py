import os

import inject

from common.consul import ConsulClient
from config import ROOT_LOG
from injector import configure_injector, CRM
from mco.utils import get_own_ip
from microcore.base.application import Application
from supervisor.manager import Supervisor
from supervisor.state import StateMonitor


class SupervisorApp(Application):
    consul: ConsulClient = inject.attr(ConsulClient)

    async def _setup(self):
        await super()._setup()
        self.node_id = os.environ.get('BDZ_NODE_ID')
        if not self.node_id:
            raise RuntimeError('no BDZ_NODE_ID provided')
        ROOT_LOG.info('node_id is [%s]', self.node_id)
        await self.consul.official.agent.service.register(
            'wsp_worker_%s' % self.node_id,
            address=get_own_ip()
        )

        self.manager = Supervisor(
            program=os.environ.get('BDZ_PROGRAM'),
            state_monitor=StateMonitor(
                node_id=self.node_id,
                loop=self._loop
            ),
            loop=self._loop
        )
        await self.manager.start()

    async def _shutdown(self):
        await self.consul.official.agent.service.deregister(
            service_id='wsp_worker_%s' % self.node_id
        )

        await self.manager.stop()
        await CRM.close_all()
        await super()._shutdown()


if __name__ == '__main__':
    ROOT_LOG.info('starting...')
    configure_injector()
    SupervisorApp().run()
