from common.application_mixin import CommonAppMixin
from config import KAFKA_DSN, ROOT_LOG
from sampling.api import SamplerAPI
from sampling.producer import LoadGeneratorProducerManager


class SamplerApplication(CommonAppMixin):
    async def _setup(self):
        await super()._setup()

        self.lgm = LoadGeneratorProducerManager(
            servers=KAFKA_DSN,
            loop=self._loop
        )

        self.add_routes_from(SamplerAPI(
            manager=self.lgm
        ))
        self.cors_add_all()

    async def _shutdown(self):
        await super()._shutdown()
        await self.lgm.stop()


if __name__ == '__main__':
    ROOT_LOG.info('starting [%s]', SamplerApplication.__name__)
    SamplerApplication().run()
