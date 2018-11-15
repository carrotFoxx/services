# setup logging
import asyncio
import logging
import os
import sys
from datetime import timedelta

from uvloop import EventLoopPolicy

from microcore.base.log import LogSetup
from microcore.storage.mongo import motor

asyncio.set_event_loop_policy(EventLoopPolicy())

PLATFORM_VERSION = os.getenv('PLATFORM_VERSION', 'unknown')

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

CONSUL_DSN = os.environ.get('CONSUL_DSN', 'http://consul:8500')
CONSUL_SUBORDINATE_DIR = '/buldozer/subordinate/'

KAFKA_DSN = os.environ.get('KAFKA_DSN', 'kafka:9092')

KAFKA_DEFAULT_INCOMING_TOPIC = 'events'
KAFKA_DEFAULT_OUTGOING_TOPIC = 'bdz_wsp_results'

# supervisor settings
SPV_STATE_RESYNC_INTERVAL = 60
SPV_STATE_KEY_DESIRED_VERSION = 'desired_version'
SPV_STATE_KEY_ADOPTED_VERSION = 'adopted_version'

# mounted folder path / shared fs volume mount to strip/add
SHARED_FS_MOUNT_PATH = os.getenv('SHARED_FS_MOUNT_PATH', '/opt/data/')
SHARED_STORAGE_FILE_PATH_TPL = os.path.join(SHARED_FS_MOUNT_PATH, 'files/%s')
