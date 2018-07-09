import uuid

import pytest

from common.entity.scenario import Scenario
from microcore.base.repository import DoesNotExist
from scenario.adapters import ScenarioMongoStorageAdapter

SCN_UID = str(uuid.uuid4())


@pytest.fixture(scope='module')
def adapter():
    return ScenarioMongoStorageAdapter()


@pytest.mark.asyncio
async def test_1_save(adapter: ScenarioMongoStorageAdapter):
    scn = Scenario(
        uid=SCN_UID,
        slug='test_doc',
        root={
            'a': [1, 2, 3],
            'b': 'prop',
            'c': {
                'abstract': None
            }
        }
    )

    res = await adapter.save(scn)
    assert res


@pytest.mark.asyncio
async def test_2_find(adapter: ScenarioMongoStorageAdapter):
    res = await adapter.find({'slug': 'test_doc'})
    for o in res:
        assert isinstance(o, Scenario)


@pytest.mark.asyncio
async def test_3_load(adapter: ScenarioMongoStorageAdapter):
    res = await adapter.load(SCN_UID)
    assert isinstance(res, Scenario)


@pytest.mark.asyncio
async def test_4_update(adapter: ScenarioMongoStorageAdapter):
    res: Scenario = await adapter.load(SCN_UID)
    v_before_update = res.document_version
    res.root['a'].append(4)
    upd_res = await adapter.save(res)
    assert upd_res
    assert res.document_version - v_before_update == 1


@pytest.mark.asyncio
async def test_5_delete(adapter: ScenarioMongoStorageAdapter):
    assert await adapter.delete(SCN_UID)
    with pytest.raises(DoesNotExist):
        res: Scenario = await adapter.load(SCN_UID)
