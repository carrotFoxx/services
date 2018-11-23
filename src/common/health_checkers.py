import aiohttp
import inject
import urllib3
from aiohttp import ClientResponse, hdrs

from common.consul import ConsulClient
from common.healthcheck import ComponentImportance, ComponentType, HealthCheckComponent, MetricType, component_name
from config import MONGO_DB, SENTRY_DSN


async def check_mongo_available() -> (bool, str):
    await MONGO_DB.command('ismaster')
    return True, 'successful round-trip to mongodb server'


mongo_available = HealthCheckComponent(
    component_name=component_name('mongodb', MetricType.CONNECTIVITY),
    check_function=check_mongo_available,
    component_type=ComponentType.DATASTORE.value,
    success_ttl=30,
    failure_ttl=10
)


@inject.params(consul=ConsulClient)
async def check_consul_available(consul: ConsulClient) -> (bool, str):
    async with consul._client.get(
            **consul._req('/v1/status/leader')
    ) as response:  # type: ClientResponse
        if response.status == 200:
            return True, 'successful round-trip to consul'
        return False, 'consul responded with code=%s' % response.status


consul_available = HealthCheckComponent(
    component_name=component_name('consul', MetricType.CONNECTIVITY),
    check_function=check_consul_available,
    success_ttl=30,
    failure_ttl=10
)

_sentry_health_url = None


def _get_sentry_health_url() -> str:
    global _sentry_health_url
    if not _sentry_health_url:
        url = urllib3.util.parse_url(SENTRY_DSN)
        _sentry_health_url = str(urllib3.util.Url(
            scheme=url.scheme,
            host=url.host,
            port=url.port,
            path='/api/0/'))
    return _sentry_health_url


async def check_sentry_reachable() -> (bool, str):
    if not SENTRY_DSN:
        return True, 'sentry not configured, wherefore not required'
    async with aiohttp.request(hdrs.METH_HEAD, _get_sentry_health_url()) as response:
        if response.status == 200:
            return True, 'successful round-trip to sentry'
        return False, 'sentry responded with code=%s' % response.status


sentry_reachable = HealthCheckComponent(
    component_name('sentry', MetricType.CONNECTIVITY),
    check_function=check_sentry_reachable,
    component_type=ComponentType.SYSTEM.value,
    importance=ComponentImportance.CONCERN,
    success_ttl=5 * 60,
    failure_ttl=60
)
