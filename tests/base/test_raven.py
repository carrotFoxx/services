import asyncio

from microcore.base.log import raven_client


def test_raven_report_exception():
    async def test():
        try:
            1 / 0
        except:
            raven_client.captureException()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(test())
    loop.run_until_complete(asyncio.gather(*asyncio.Task.all_tasks(loop=loop)))
    loop.close()
