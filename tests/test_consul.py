import logging
from pprint import pformat

import pytest

from common.consul import CatalogServiceNode, ConsulClient, KVData

logger = logging.getLogger()


@pytest.fixture(scope='module')
async def client(event_loop) -> ConsulClient:
    c = ConsulClient(
        base='http://localhost:8500/v1/',
        loop=event_loop
    )
    yield c

    await c.close()
    del c


@pytest.mark.asyncio
async def test_get_service(client: ConsulClient):
    nodes = await client.catalog.service_nodes('consul')
    for x in nodes:
        assert isinstance(x, CatalogServiceNode)
        assert x.service_name == 'consul'


@pytest.mark.asyncio
async def test_kv_store(client: ConsulClient):
    # put some values
    kv = client.kv
    await kv.put('custom-data/prop1', 123)
    await kv.put('custom-data/prop2', 'abstract string value')
    await kv.put('custom-data/prop3', [1, 2, 3])

    # get values
    value = await kv.get('custom-data/prop1', raw=True)
    assert value == '123'
    value = await kv.get('custom-data/prop2')
    assert value.key == 'custom-data/prop2'

    # get list
    values = await kv.get_all('custom-data/')
    assert isinstance(values, list)
    assert len(values) == 3
    for x in values:
        assert isinstance(x, KVData)
        assert x.key.startswith('custom-data/')

    values = await kv.get_all('custom-data/', raw=True)
    assert isinstance(values, dict)
    assert len(values) == 3
    logging.info('get_all:\n%s', pformat(values))
    for x in values:
        assert isinstance(x, str)

    await kv.rem('custom-data', recurse=True)
