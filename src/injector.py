from typing import Callable

import inject


def global_configuration(binder: inject.Binder):
    pass


def configure_injector(configuration: Callable[[inject.Binder], None]):
    def conf_aggregate(binder: inject.Binder):
        global_configuration(binder)
        configuration(binder)

    inject.configure(conf_aggregate)
