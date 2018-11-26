import asyncio
import logging
import time
import uuid
from datetime import datetime
from enum import Enum, IntEnum, auto
from typing import Any, Awaitable, Callable, Dict, List, Tuple

import attr
from aiohttp import hdrs
from aiohttp.web_request import Request
from aiohttp.web_response import json_response
from aiohttp.web_urldispatcher import UrlDispatcher

from config import PLATFORM_VERSION
from microcore.base.application import Routable

log = logging.getLogger(__name__)


class MetricType(Enum):
    """
    common metric names according to RFC
    """
    UTILIZATION = 'utilization'
    RESPONSIVENESS = 'responseTime'
    CONNECTIVITY = 'connections'
    UPTIME = 'uptime'


class ComponentType(Enum):
    """
    common component types according to RFC
    """
    COMPONENT = 'component'
    DATASTORE = 'datastore'
    SYSTEM = 'system'


class ObservedUnit(Enum):
    MICROSECONDS = 'msec'
    SECONDS = 'sec'
    MINUTES = 'min'


class HealthStatus(str, Enum):
    """
    possible check states according to RFC
    """
    PASSING = 'pass'
    FAILING = 'fail'
    WARNING = 'warn'


class ComponentImportance(IntEnum):
    INFORMATIONAL = auto()
    CONCERN = auto()
    CRITICAL = auto()


def component_name(name: str, check_type: MetricType = None):
    if check_type:
        if check_type in MetricType:
            check_type = check_type.value
        name += f':{check_type}'
    return name


@attr.s(auto_attribs=True)
class HealthCheckComponent:
    component_name: str
    check_function: Callable[[], Awaitable[Tuple[bool, str]]]

    component_type: str = ComponentType.COMPONENT.value

    importance: ComponentImportance = ComponentImportance.CRITICAL

    success_ttl: int = 0
    failure_ttl: int = 0

    component_id: str = attr.Factory(lambda: str(uuid.uuid4()))

    status: HealthStatus = HealthStatus.PASSING
    time: datetime = None

    observed_value: Any = None
    observed_unit: str = None
    output: str = None

    def as_dict(self) -> dict:
        dct = {
            'component_id': self.component_id,
            'component_name': self.component_name,
            'component_type': self.component_type,
            'status': self.status.value,
            'time': self.time.isoformat(),
        }
        if self.observed_value is not None:
            dct['observed_value'] = self.observed_value
            dct['observed_unit'] = self.observed_unit
        if self.output is not None:
            dct['output'] = self.output
        return dct


class HealthCheckService:
    def __init__(self,
                 check_timeout=5,
                 loop: asyncio.AbstractEventLoop = None) -> None:
        super().__init__()
        self.check_timeout = int(check_timeout or 5)
        self._loop = loop or asyncio.get_event_loop()
        self._components: Dict[str, HealthCheckComponent] = {}
        self._cache: Dict[str, float] = {}
        self._status = HealthStatus.WARNING

    def add_check(self, component: HealthCheckComponent):
        self._components[component.component_name] = component

    async def check(self) -> (HealthStatus, List[HealthCheckComponent]):
        units = [
            self.run_check(name)
            for name in self._components
            if (name in self._cache and self._cache[name] <= time.time()) or name not in self._cache
        ]
        if len(units) > 0:
            results: List[(str, float)] = await asyncio.gather(
                *units,
                loop=self._loop,
                return_exceptions=False
            )
            for name, expires in results:  # write cache information
                self._cache[name] = expires

        # recalculate overall status over all cache values
        status = HealthStatus.PASSING
        for component in self._components.values():
            if component.status is HealthStatus.FAILING:
                status = HealthStatus.FAILING
                break
            if component.status is HealthStatus.WARNING:
                status = HealthStatus.WARNING

        self._status = status
        return status, list(self._components.values())

    async def run_check(self, name: str):
        component = self._components[name]
        # noinspection PyBroadException
        try:
            passed, output = await asyncio.wait_for(
                component.check_function(),
                timeout=self.check_timeout
            )
        except asyncio.TimeoutError:
            passed, output = False, 'checker: timed out (limit=%ss)' % self.check_timeout
        except Exception as e:
            log.exception('health check failed')
            passed, output = self.exception_handler(name, e)

        if not passed:
            msg = 'Health check "{}" failed with output "{}"'.format(name, output)
            log.warning(msg)

        # cache options
        timestamp = time.time()
        expires = timestamp + float(component.success_ttl if passed else component.failure_ttl)

        # update component state
        if passed:
            component.status = HealthStatus.PASSING
        elif not passed and component.importance < ComponentImportance.CRITICAL:
            component.status = HealthStatus.WARNING
        else:
            component.status = HealthStatus.FAILING

        component.time = datetime.fromtimestamp(timestamp)
        component.output = output

        return component.component_name, expires

    @staticmethod
    def exception_handler(_: str, e: Exception):
        return False, f'{str(type(e))}:{str(e)}'

    def cache_max_age(self):
        if len(self._components) == 0:
            return 60
        if self._status is HealthStatus.PASSING:
            return min([c.success_ttl for c in self._components.values()])
        return min([c.failure_ttl for c in self._components.values()])


class HealthCheckAPI(Routable):

    def __init__(self, service: HealthCheckService) -> None:
        super().__init__()
        self.service = service
        self._version, self._release = PLATFORM_VERSION.split('+', 1) \
            if '+' in PLATFORM_VERSION else (PLATFORM_VERSION, 'unknown')

    def set_routes(self, router: UrlDispatcher):
        router.add_get('/health', self.handler)

    async def handler(self, _: Request):
        status, states = await self.service.check()
        max_age = self.service.cache_max_age()

        if status is HealthStatus.PASSING:
            code, reason = 200, 'OK'
        elif status is HealthStatus.WARNING:
            code, reason = 207, 'WARN'
        else:
            code, reason = 500, 'NOT OK'

        return json_response(
            headers={hdrs.CACHE_CONTROL: f'max-age={int(max_age)}'},
            content_type='application/health+json',
            status=code,
            reason=reason,
            data={
                'status': status,
                'version': self._version,
                'release': self._release,
                'details': [check.as_dict() for check in states]
            }
        )
