import os

from common import health_checkers
from common.application_mixin import CommonAppMixin
from config import KAFKA_DSN, MONGO_DB, ROOT_LOG
from persistence.consumer import FailurePolicy, PersistenceConsumerManager
from persistence.writer import MongoWriter


class PersistenceManagerApplication(CommonAppMixin):
    async def _setup(self):
        await super()._setup()

        self.pcm = PersistenceConsumerManager(
            servers=KAFKA_DSN,
            loop=self._loop
        )

        self.writer = MongoWriter(
            db=MONGO_DB
        )

        self.pcm.add_consumer(
            topic=os.environ.get('BDZ_CONSUMER_TOPIC', 'bdz_wsp_results'),
            group_id=os.environ.get('BDZ_CONSUMER_GROUP_ID', 'bdz_default_cg'),
            persist_func=self.writer.process,
            policy=FailurePolicy.SHUTDOWN
        )
        self.health_check_service.add_check('mongodb', health_checkers.check_mongo_available)

    async def _shutdown(self):
        await self.pcm.stop()
        await super()._shutdown()


if __name__ == '__main__':
    ROOT_LOG.info('starting [%s]', PersistenceManagerApplication.__name__)
    PersistenceManagerApplication().run()
