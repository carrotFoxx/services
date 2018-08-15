import logging
from typing import Any, Callable

import inject

logger = logging.getLogger(__name__)

_CLOSABLE = []


def closable(cls: Any):
    _CLOSABLE.append(cls)
    logger.debug('register closable: %s', cls)
    return cls


def close_registered(closer: callable):
    for x in _CLOSABLE:
        closer(inject.instance(x))
        logger.debug('closed: %s', x)


async def async_close_registered(closer: callable):
    for x in _CLOSABLE:
        await closer(inject.instance(x))
        logger.debug('closed: %s', x)


def global_configuration(binder: inject.Binder):
    pass


def configure_injector(configuration: Callable[[inject.Binder], None] = None):
    def conf_aggregate(binder: inject.Binder):
        global_configuration(binder)
        if configuration is not None:
            configuration(binder)

    inject.configure(conf_aggregate)
