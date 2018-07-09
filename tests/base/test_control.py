import asyncio
import logging

import pytest

from microcore.base.control import AsyncIODelayedCallManager, AsyncIOTaskManager


@pytest.mark.asyncio
async def test_delayed_call_manager(event_loop: asyncio.AbstractEventLoop):
    mgr = AsyncIODelayedCallManager(
        op_callback=lambda *args: logging.info('delayed call with %s', args),
        delay=1,
        loop=event_loop
    )

    mgr.add('d1', 1, 2, 3)
    assert len(mgr._handles) == 1
    await asyncio.sleep(2)
    assert len(mgr._handles) == 0

    mgr.add('d2', 4, 5, 6)
    assert len(mgr._handles) == 1
    mgr.remove('d2')
    assert len(mgr._handles) == 0
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_task_manager(event_loop: asyncio.AbstractEventLoop):
    async def subtask(*args):
        logging.info('delayed task with %s', args)
        await asyncio.sleep(1)
        logging.info('delayed task finished')

    mgr = AsyncIOTaskManager(
        op_callback=subtask,
        loop=event_loop
    )

    mgr.add('d1', 1, 2, 3)
    assert len(mgr._handles) == 1
    await asyncio.sleep(2)
    assert len(mgr._handles) == 0

    mgr.add('d2', 4, 5, 6)
    assert len(mgr._handles) == 1
    await asyncio.sleep(0)
    mgr.remove('d2')
    assert len(mgr._handles) == 0
