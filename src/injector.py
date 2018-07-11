from typing import Callable

import inject


def global_configuration(binder: inject.Binder):
    pass


def configure_injector(configuration: Callable[[inject.Binder], None] = None):
    def conf_aggregate(binder: inject.Binder):
        global_configuration(binder)
        if configuration is not None:
            configuration(binder)

    inject.configure(conf_aggregate)
