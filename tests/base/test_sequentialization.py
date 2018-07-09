import asyncio
import datetime
import random
from unittest import TestCase

from microcore.base.sequentialization import SequentialExecutionManager


class TestSequentialExecutionManager(TestCase):

    @staticmethod
    async def variadic_time_handler(item):
        random_time = random.randint(1, 3)
        print('handling %s for %s sec' % (item, random_time))
        await asyncio.sleep(random_time)

    def test_handle(self):
        loop = asyncio.get_event_loop()

        manager = SequentialExecutionManager(
            reaper_interval=10,
            reap_after=datetime.timedelta(seconds=10),
            handler=self.variadic_time_handler
        )

        async def launch_tasks():
            for i in range(5):
                for j in range(5):
                    await manager.handle(str(i), f't{i}:i{j}')

        async def test():
            await launch_tasks()
            await asyncio.sleep(40)
            self.assertLess(len(manager._threads), 5)
            await manager.stop()
            self.assertEqual(len(manager._threads), 0)

        loop.run_until_complete(test())

        tasks = asyncio.Task.all_tasks(loop=loop)
        loop.run_until_complete(
            asyncio.wait_for(
                asyncio.gather(*tasks),
                5
            )
        )

    def test_stop(self):
        loop = asyncio.get_event_loop()

        manager = SequentialExecutionManager(
            reaper_interval=10,
            reap_after=datetime.timedelta(seconds=10),
            handler=self.variadic_time_handler
        )

        async def launch_tasks():
            for i in range(5):
                for j in range(5):
                    await manager.handle(str(i), f't{i}:i{j}')

        async def test():
            await launch_tasks()
            await asyncio.sleep(8)
            await manager.stop()
            self.assertEqual(len(manager._threads), 0)

        loop.run_until_complete(test())

        tasks = asyncio.Task.all_tasks(loop=loop)
        loop.run_until_complete(
            asyncio.wait_for(
                asyncio.gather(*tasks),
                5
            )
        )

        loop.close()


class TestSequentialTread(TestCase):
    pass
