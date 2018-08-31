import inspect
import logging
from asyncio import CancelledError
from typing import Tuple, Type, Union


def _is_coroutine(fn):
    return inspect.iscoroutinefunction(fn) or inspect.isasyncgenfunction(fn)


def convert_exceptions(fn_or_none=None, *,
                       exc: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception,
                       to: Type[Exception] = RuntimeError):
    def decorator(fn):
        def sync_wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except exc as e:
                raise to(str(e)) from e

        async def async_wrapper(*args, **kwargs):
            try:
                return await fn(*args, **kwargs)
            except exc as e:
                raise to(str(e)) from e

        return sync_wrapper if not _is_coroutine(fn) else async_wrapper

    return decorator(fn_or_none) if fn_or_none else decorator


_SENTINEL = object()


def default_on_error(fn_or_none=None, *,
                     exc: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception):
    def decorator(fn):
        def sync_wrapper(*args, default=_SENTINEL, **kwargs):
            try:
                return fn(*args, **kwargs)
            except exc:
                if default is not _SENTINEL:
                    return default
                raise

        async def async_wrapper(*args, default=_SENTINEL, **kwargs):
            try:
                return await fn(*args, **kwargs)
            except exc:
                if default is not _SENTINEL:
                    return default
                raise

        return sync_wrapper if not _is_coroutine(fn) else async_wrapper

    return decorator(fn_or_none) if fn_or_none else decorator


def log_exceptions(fn_or_none=None, *,
                   exc: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception):
    """
    log raised exceptions (except for CancelledError for coroutines) and fail silently
    """

    def decorator(fn):
        def sync_wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except exc:
                logging.exception('muted exception')

        async def async_wrapper(*args, **kwargs):
            try:
                return await fn(*args, **kwargs)
            except (CancelledError, GeneratorExit):
                raise
            except exc:
                logging.exception('muted exception')

        return sync_wrapper if not _is_coroutine(fn) else async_wrapper

    return decorator(fn_or_none) if fn_or_none else decorator
