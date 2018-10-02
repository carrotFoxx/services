import os

from config import KAFKA_DSN, MONGO_DB, ROOT_LOG
from microcore.base.application import Application
from persistence.consumer import PersistenceConsumerManager, FailurePolicy
from persistence.writer import MongoWriter


class PersistenceManagerApplication(Application):
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
            topic='bdz_wsp_results',
            group_id=os.environ.get('BDZ_CONSUMER_GROUP_ID', 'bdz_default_cg'),
            persist_func=self.writer.process,
            policy=FailurePolicy.SHUTDOWN
        )

    async def _shutdown(self):
        await self.pcm.stop()
        await super()._shutdown()


if __name__ == '__main__':
    ROOT_LOG.info('starting [%s]', PersistenceManagerApplication.__name__)
    PersistenceManagerApplication().run()
