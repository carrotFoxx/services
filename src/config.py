# setup logging
import os
import sys

from microcore.base.log import LogSetup

PLATFORM_VERSION = LogSetup.get_platform_version()

LOG_LEVEL = LogSetup.detect()

LogSetup.setup_logs(LOG_LEVEL)

SENTRY_DSN = os.environ.get('SENTRY_DSN', None)
SENTRY_NAME = os.environ.get('SENTRY_NAME', 'Buldozer Platform')
_inferred_site = sys.argv[0].split('/').pop().rstrip('.py')
SENTRY_SITE = os.environ.get('SENTRY_SITE', _inferred_site)
APP_ENV = os.environ.get('APP_ENV', 'staging')

# initialize Sentry reporting only if SENTRY_DSN provided
if SENTRY_DSN:
    _raven_client = LogSetup.setup_sentry(
        dsn=SENTRY_DSN,
        name=SENTRY_NAME,
        site=SENTRY_SITE,
        env=APP_ENV,
        version=PLATFORM_VERSION
    )