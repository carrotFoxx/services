import asyncio
import logging
import time
from typing import Awaitable, Callable, Dict, List, Tuple, Union

import attr
from aiohttp.web_request import Request
from aiohttp.web_response import json_response
from aiohttp.web_urldispatcher import UrlDispatcher

from microcore.base.application import Routable

log = logging.getLogger(__name__)


@attr.s(auto_attribs=True)
class CheckStatus:
    name: str
    passed: bool = False
    output: str = None
    timestamp: float = 0
    expires: float = 0


class HealthCheckService:
    def __init__(self,
                 success_ttl=None,
                 failure_ttl=None,
                 check_timeout=5,
                 loop: asyncio.AbstractEventLoop = None) -> None:
        super().__init__()
        self.check_timeout = int(check_timeout or 5)
        self.success_ttl = float(success_ttl or 0)
        self.failure_ttl = float(failure_ttl or 0)
        self._loop = loop or asyncio.get_event_loop()
        self._checks: Dict[str, Callable[[], Awaitable[Tuple[bool, dict]]]] = {}
        self._cache: Dict[str, CheckStatus] = {}

    def add_check(self, name: str, check: Callable[[], Awaitable[Tuple[bool, Union[str, dict]]]]):
        self._checks[name] = check

    async def check(self) -> (bool, List[CheckStatus]):
        units = [
            self.run_check(name)
            for name in self._checks
            if (name in self._cache and self._cache[name].expires <= time.time()) or name not in self._cache
        ]
        if len(units) > 0:
            results: List[CheckStatus] = await asyncio.gather(
                *units,
                loop=self._loop,
                return_exceptions=False
            )
            for status in results:  # write all states to cache
                self._cache[status.name] = status

        # recalculate overall status over all cache values
        overall_passed = True
        for status in self._cache.values():
            overall_passed = overall_passed and status.passed
        return overall_passed, list(self._cache.values())

    async def run_check(self, name: str) -> CheckStatus:
        # noinspection PyBroadException
        try:
            passed, output = await asyncio.wait_for(self._checks[name](), timeout=self.check_timeout)
        except asyncio.TimeoutError:
            passed, output = False, 'checker: timed out (limit=%ss)' % self.check_timeout
        except Exception as e:
            log.exception('health check failed')
            passed, output = self.exception_handler(name, e)

        if not passed:
            msg = 'Health check "{}" failed with output "{}"'.format(name, output)
            log.error(msg)

        timestamp = time.time()
        if passed:
            expires = timestamp + self.success_ttl
        else:
            expires = timestamp + self.failure_ttl

        return CheckStatus(
            name=name,
            passed=passed,
            output=output,
            timestamp=timestamp,
            expires=expires
        )

    @staticmethod
    def exception_handler(_: str, e: Exception):
        return False, f'{str(type(e))}:{str(e)}'


class HealthCheckAPI(Routable):

    def __init__(self, service: HealthCheckService) -> None:
        super().__init__()
        self.service = service

    def set_routes(self, router: UrlDispatcher):
        router.add_get('/health', self.handler)

    async def handler(self, _: Request):
        passed, states = await self.service.check()
        return json_response(
            data={
                'status': 'ok' if passed else 'not ok',
                'timestamp': time.time(),
                'results': [attr.asdict(check) for check in states]
            },
            status=200 if passed else 500
        )
