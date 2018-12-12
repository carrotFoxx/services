from common.application_mixin import CommonAppMixin
from config import KAFKA_DSN, ROOT_LOG
from microcore.base.repository import Repository
from microcore.storage.mongo import motor
from microcore.web.owned_api import OwnedMiddlewareSet
from sampling.adapters import RetrospectiveMongoStorageAdapter
from sampling.api import RetrospectiveGeneratorAPI, SamplerAPI
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
        self.add_routes_from(RetrospectiveGeneratorAPI(
            manager=self.lgm,
            source_db=motor().events,
            repository=Repository(RetrospectiveMongoStorageAdapter())
        ))

        self.cors_add_all()

        self.server.middlewares.append(OwnedMiddlewareSet.extract_owner)

    async def _shutdown(self):
        await super()._shutdown()
        await self.lgm.stop()


if __name__ == '__main__':
    ROOT_LOG.info('starting [%s]', SamplerApplication.__name__)
    SamplerApplication().run()
