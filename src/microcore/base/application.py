import asyncio
import logging
import signal
from asyncio.events import AbstractEventLoop
from asyncio.futures import CancelledError

from aiohttp import web
from aiohttp.web_urldispatcher import UrlDispatcher

logger = logging.getLogger(__name__)


class Application:
    """
    :type _loop : asyncio.AbstractEventLoop
    """

    def __init__(self, loop=None):
        super().__init__()
        self._loop = loop or asyncio.get_event_loop()
        self._loop.set_exception_handler(self._exception_handler)

    @staticmethod
    def _exception_handler(loop: AbstractEventLoop, context):
        # ‘message’: Error message;
        # ‘exception’ (optional): Exception object;
        # ‘future’ (optional): asyncio.Future instance;
        # ‘handle’ (optional): asyncio.Handle instance;
        # ‘protocol’ (optional): Protocol instance;
        # ‘transport’ (optional): Transport instance;
        # ‘socket’ (optional): socket.socket instance.
        message = context.get('message')
        if not message:
            message = 'Unhandled exception in event loop'

        exception = context.get('exception')  # type: Exception
        if exception is not None:
            exc_info = (type(exception), exception, exception.__traceback__)
            logger.exception(message, exc_info=exc_info)
        else:
            logger.error(message)

        return loop.default_exception_handler(context)

    def signal_sigterm_handle(self, signal_name):
        """SIGNAL HANDLING"""
        logger.info("signal [%s] received, begin shutdown process", signal_name)
        self._loop.stop()

    def register_signal_handlers(self):
        for signal_name in ('SIGINT', 'SIGTERM', 'SIGHUP'):
            logger.debug('registering signal handler for: %s', signal_name)
            self._loop.add_signal_handler(getattr(signal, signal_name),
                                          lambda: self.signal_sigterm_handle(signal_name))

    async def _setup(self):
        logger.debug('execute setup hooks')
        self.register_signal_handlers()

    async def _shutdown(self):
        logger.debug('execute shutdown hooks')
        pass

    def run(self):
        try:
            self._loop.run_until_complete(self._setup())
            self._loop.run_forever()
        except KeyboardInterrupt:
            pass
        finally:
            self._loop.run_until_complete(self._shutdown())
            # wait tasks left to complete
            try:
                self._loop.run_until_complete(
                    asyncio.wait_for(
                        asyncio.gather(*asyncio.Task.all_tasks(loop=self._loop)),
                        10
                    )
                )
            except TimeoutError:
                logger.error('shutdown process taken too long, not all task were completed')
            except (CancelledError, GeneratorExit):
                logger.info('some of remaining ops got cancelled, its normal')
            self._loop.close()


class Routable:
    def set_routes(self, router: UrlDispatcher):
        raise NotImplemented()


class WebApplication(Application):
    """
    :type server : aiohttp.web.Application
    """

    def __init__(self, host='0.0.0.0', port=8080, **kwargs):
        super().__init__(**kwargs)
        self.host = host
        self.port = port
        self.server = web.Application(loop=self._loop)

    def setup_router(self, mapper_fn):
        mapper_fn(self.server.router)

    def add_routes_from(self, routable: Routable):
        routable.set_routes(self.server.router)

    async def _setup(self):
        await super()._setup()

        async def _shutdown_signal_handler(app):
            await self._shutdown()

        self.server.on_shutdown.append(_shutdown_signal_handler)

    def run(self):
        self._loop.run_until_complete(self._setup())
        web.run_app(self.server, host=self.host, port=self.port)
