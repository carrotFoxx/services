import inject
from aiohttp import ClientResponse

from common.consul import ConsulClient


async def check_mongo_available() -> (bool, str):
    from config import MONGO_DB
    await MONGO_DB.command('ismaster')
    return True, 'successful round-trip to mongodb server'


@inject.params(consul=ConsulClient)
async def check_consul_available(consul: ConsulClient) -> (bool, str):
    async with consul._client.get(
            **consul._req('/v1/status/leader')
    ) as response:  # type: ClientResponse
        if response.status == 200:
            return True, 'successful round-trip to consul'
        return False, 'consul responded with code=%s' % response.status
