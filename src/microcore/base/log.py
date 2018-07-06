import argparse
import logging
import os
import sys
from typing import Type, Union

from raven import Client
from raven.handlers.logging import SentryHandler
from raven.transport.base import Transport
from raven_aiohttp import AioHttpTransport

logger = logging.getLogger()


class LogSetup:
    @staticmethod
    def setup_logs(level=logging.INFO):
        logging.basicConfig(stream=sys.stdout, format="[%(asctime)s]:" + logging.BASIC_FORMAT, level=level)
        logger.info('logger set up with level: %s', logging._levelToName.get(level, level))

    # noinspection PyProtectedMember
    @staticmethod
    def detect_level(level: Union[str, int]):
        if isinstance(level, int):
            return logging._checkLevel(level)
        if not isinstance(level, str):
            raise ValueError('cannot determine level from [%s] type', type(level))
        if level.isdigit():
            return logging._checkLevel(int(level))
        return logging._checkLevel(level)

    class NoOpTransport(Transport):
        scheme = ['sync+noop']

        # noinspection PyUnusedLocal
        def __init__(self, timeout=0, verify_ssl=True, ca_certs=None):
            self.timeout = 0
            self.verify_ssl = True
            self.ca_certs = None

        def send(self, url, data, headers):
            pass

    sentry_transport: Type[Transport] = NoOpTransport

    @classmethod
    def setup_sentry(cls, dsn, name, site, env, version=None) -> Client:
        if dsn is not None:
            cls.sentry_transport = AioHttpTransport

        version = version or cls.get_platform_version()
        tags = {}

        raven = Client(
            dsn,
            transport=cls.sentry_transport,
            release=version,
            install_logging_hook=True,
            install_sys_hook=True,
            name=name,
            site=site,
            environment=env,
            tags=tags,
            include_paths=['reasonai_dm', 'raven_aiohttp']
        )

        raven_logging_handler = SentryHandler(client=raven, level=logging.ERROR)
        logger.addHandler(raven_logging_handler)

        return raven

    @staticmethod
    def get_platform_version() -> str:
        try:
            with open(os.path.dirname(os.path.realpath(__file__)) + '/../../version.info') as fd:
                return fd.read().strip()
        except FileNotFoundError:
            return 'unknown'


# cli args
cli_parser = argparse.ArgumentParser(description="PLATFORM init")
cli_parser.add_argument('--debug', type=int, default=None, dest='debug')
cli_args, _ = cli_parser.parse_known_args()

# noinspection PyProtectedMember
level_env = LogSetup.detect_level(os.environ.get('LOG_LEVEL', logging.INFO))
level_cli = LogSetup.detect_level(cli_args.debug) if cli_args.debug is not None else None

LOG_LEVEL = level_cli if level_cli is not None else level_env

# setup logging
LogSetup.setup_logs(LOG_LEVEL)

SENTRY_DSN = os.environ.get('SENTRY_DSN', None)
inferred_site = sys.argv[0].split('/').pop().rstrip('.py')
SENTRY_NAME = os.environ.get('SENTRY_NAME', 'Platform')
SENTRY_SITE = os.environ.get('SENTRY_SITE', inferred_site)
SENTRY_ENV = os.environ.get('APP_ENV', 'staging')

# initialize Sentry reporting only if SENTRY_DSN provided
if SENTRY_DSN:
    raven_client = LogSetup.setup_sentry(
        dsn=SENTRY_DSN,
        name=SENTRY_NAME,
        site=SENTRY_SITE,
        env=SENTRY_ENV
    )

PLATFORM_VERSION = LogSetup.get_platform_version()

__all__ = (
    'logger',
    'LOG_LEVEL',
    'SENTRY_ENV',
    'PLATFORM_VERSION'
)
