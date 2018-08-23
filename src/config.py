# setup logging
import logging
import os
import sys
from datetime import timedelta

from microcore.base.log import LogSetup
from microcore.storage.mongo import motor

PLATFORM_VERSION = LogSetup.get_platform_version()

LOG_LEVEL = LogSetup.detect()

# if CONTAINERPILOT_PID env var present we disable timestamps in log
# (ContainerPilot adds them then translating logs to stdout)
enable_timed_logs = not bool(os.environ.get('CONTAINERPILOT_PID', False))
LogSetup.setup_logs(LOG_LEVEL, timed_logs=enable_timed_logs)

ROOT_LOG = logging.getLogger()

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

MONGO_DB = motor().buldozer

WSP_GC_COLLECT_DELAY = timedelta(seconds=int(os.getenv('WSP_GC_COLLECT_DELAY', 60 * 60)))
WSP_GC_INTERVAL = int(os.getenv('WSP_GC_INTERVAL', 600))
