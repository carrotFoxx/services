from unittest import TestCase
from uuid import uuid4

from microcore.base.repository import DoesNotExist
from microcore.entity.encoders import proxy_encoder_instance
from microcore.storage.redis import REDIS_DSN, Redis, SimpleRedisStorageAdapter
from tests import EntityTest, run_async


class TestRedis(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.redis = Redis(dsn=REDIS_DSN, db=1)

    @run_async
    async def test_connection(self):
        async with self.redis as r:
            uuid = str(uuid4())
            await r.set('test_key', uuid)
            data = await r.info()
            ret: str = await r.get('test_key')
            self.assertEqual(uuid, ret)

        self.assertIn('db1', data['keyspace'])
        self.assertGreaterEqual(int(data['keyspace']['db1']['keys']), 1)


class TestSimpleRedisStorageAdapter(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.redis = Redis(dsn=REDIS_DSN, db=1)
        cls.adapter = SimpleRedisStorageAdapter(
            redis_instance=cls.redis,
            encoder=proxy_encoder_instance,
            key_prefix='test_',
            expire=30
        )

    @run_async
    async def test_1_save_and_load(self):
        origin = EntityTest(uid='123', child=EntityTest())
        await self.adapter.save(
            origin
        )

        async with self.redis as r:
            self.assertTrue(await r.exists(self.adapter._key_prefix + '123'))

        restore: EntityTest = await self.adapter.load(origin.uid)

        self.assertEqual(
            origin.child.uid, restore.child.uid
        )

    @run_async
    async def test_2_delete(self):
        async with self.redis as r:
            self.assertTrue(await r.exists(self.adapter._key_prefix + '123'))

            await self.adapter.delete('123')

            self.assertFalse(await r.exists(self.adapter._key_prefix + '123'))

    @run_async
    async def test_3_load_nx(self):
        with self.assertRaises(DoesNotExist):
            await self.adapter.load('456')
