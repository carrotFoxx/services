import asyncio
import logging
from typing import List, Union

import attr

logger = logging.getLogger(__name__)


@attr.s(auto_attribs=True)
class ClosableResource:
    name: str
    ref: object
    close_method: str = 'close'
    is_async: bool = False

    def close(self):
        close_method = getattr(self.ref, self.close_method)
        if self.is_async:
            logger.info('creating async closer coro for %s(%s)', type(self).__name__, self.name)
            return close_method()
        close_method()
        logger.info('closed synchronously %s(%s)', type(self).__name__, self.name)
        return True


class ClosableResourceManager:
    def __init__(self) -> None:
        self._resources: List[ClosableResource] = []

    async def close_all(self, loop: asyncio.AbstractEventLoop = None):
        loop = loop or asyncio.get_event_loop()
        logger.info('closing registered resources...')
        handles = [resource.close() for resource in self._resources]
        async_handles = [h for h in handles if h is not True]
        await asyncio.gather(*async_handles, loop=loop)
        logger.info('closed all registered resources')

    def register(self, resource: ClosableResource):
        self._resources.append(resource)
        logger.info('registered new %s(%s)', type(resource).__name__, resource.name)

    def provider(self, name: Union[str, type], constructor: callable = None, closer: str = 'close', is_async=False):
        """
        :returns: params for inject lib `bind_to_*` functions
        """

        def wrapped_constructor():
            resource = ClosableResource(
                name=name,
                ref=name() if constructor is None else constructor(),
                close_method=closer,
                is_async=is_async
            )
            self.register(resource)
            return resource.ref

        return name, wrapped_constructor

    def instance(self, *args, **kwargs):
        """
        arguments are same as for `ClosableResourceManager.provider`
        :returns: params for inject lib `bind_instance` function
        """
        name, wrapper = self.provider(*args, **kwargs)
        return name, wrapper()
