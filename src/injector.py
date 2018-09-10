from typing import Callable

import inject

from common.consul import ConsulClient
from config import CONSUL_DSN
from mco.injector import ClosableResourceManager

# singleton instance of resource manager to refer
CRM = ClosableResourceManager()


def global_configuration(binder: inject.Binder):
    binder.bind_to_constructor(*CRM.provider(ConsulClient, lambda: ConsulClient(base=CONSUL_DSN), is_async=True))


def configure_injector(configuration: Callable[[inject.Binder], None] = None):
    def conf_aggregate(binder: inject.Binder):
        global_configuration(binder)
        if configuration is not None:
            configuration(binder)

    inject.configure(conf_aggregate)
