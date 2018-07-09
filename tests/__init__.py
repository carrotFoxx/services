import asyncio
from unittest.mock import MagicMock
from uuid import uuid4

from microcore.entity.encoders import RegisteredEntityJSONEncoderBase
from microcore.entity.model import EntityMixin


def run_async(fn):
    def async_test(*args, **kwargs):
        return asyncio.get_event_loop().run_until_complete(fn(*args, **kwargs))

    return async_test


class EntityTest(EntityMixin):
    def __init__(self, uid: str = None, child: 'EntityTest' = None) -> None:
        super().__init__()
        self.uid = uid or str(uuid4())
        self.child = child


class EntityTestJSONEncoder(RegisteredEntityJSONEncoderBase):
    entity_type = EntityTest


class AsyncMock(MagicMock):
    async def __call__(self, *args, **kwargs):
        return super().__call__(*args, **kwargs)
