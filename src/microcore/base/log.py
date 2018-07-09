import argparse
import logging
import os
import sys
from typing import Type, Union

from raven import Client
from raven.handlers.logging import SentryHandler
from raven.transport.base import Transport
from raven_aiohttp import AioHttpTransport

logger = logging.getLogger(__name__)


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

    @staticmethod
    def detect(env_var='LOG_LEVEL', default_level=logging.INFO):
        """
        detects logging level from cli args or from ENV vars (cli comes first)
        :return: int level
        """
        # cli args
        cli_parser = argparse.ArgumentParser(description="PLATFORM init")
        cli_parser.add_argument('--debug', default=None, dest='debug')
        cli_args, _ = cli_parser.parse_known_args()

        level_env = LogSetup.detect_level(os.environ.get(env_var, default_level))
        level_cli = LogSetup.detect_level(cli_args.debug) if cli_args.debug is not None else None

        return level_cli if level_cli is not None else level_env
