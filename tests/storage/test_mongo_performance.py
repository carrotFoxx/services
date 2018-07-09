import asyncio
from uuid import uuid4

import pytest
from motor.core import AgnosticCollection

from microcore.storage.mongo import motor


@pytest.fixture(scope='module')
async def collection() -> AgnosticCollection:
    db = motor().experiments
    c: AgnosticCollection = db.collection_1
    await c.insert_many([{'_id': str(uuid4()), 'data': x} for x in range(1, 1000000)])
    yield c
    await c.drop()


@pytest.fixture(scope='module')
async def entry(collection: AgnosticCollection):
    e = await collection.find_one()
    return e['_id']


async def find_count(id: str, col: AgnosticCollection):
    cursor = col.find({'_id': id}, projection=False).limit(1)
    res = await cursor._refresh()
    return res == 1


async def find_one(id: str, col: AgnosticCollection):
    res = await col.find_one({'_id': id}, projection=False)
    return res is not None


def wrap(fn, event_loop):
    def run_in_loop(*args, **kwargs):
        return event_loop.run_until_complete(fn(*args, **kwargs))

    return run_in_loop


@pytest.mark.asyncio
async def test_single_find_count(entry: str, collection: AgnosticCollection):
    res = await collection.find().limit(2)._refresh()
    assert res == 2


def test_bench_find_one(benchmark, entry: str, collection: AgnosticCollection, event_loop: asyncio.AbstractEventLoop):
    benchmark(wrap(find_one, event_loop=event_loop), id=entry, col=collection)


def test_bench_find_count(benchmark, entry: str, collection: AgnosticCollection, event_loop: asyncio.AbstractEventLoop):
    benchmark(wrap(find_count, event_loop=event_loop), id=entry, col=collection)
