from common.healthcheck import HealthCheckAPI
from config import KAFKA_DSN, ROOT_LOG
from microcore.base.application import WebApplication
from sampling.api import SamplerAPI
from sampling.producer import LoadGeneratorProducerManager


class SamplerApplication(WebApplication):
    async def _setup(self):
        await super()._setup()

        self.lgm = LoadGeneratorProducerManager(
            servers=KAFKA_DSN,
            loop=self._loop
        )

        self.add_routes_from(SamplerAPI(
            manager=self.lgm
        ))

        self.add_routes_from(HealthCheckAPI())

    async def _shutdown(self):
        await super()._shutdown()
        await self.lgm.stop()


if __name__ == '__main__':
    ROOT_LOG.info('starting [%s]', SamplerApplication.__name__)
    SamplerApplication().run()
