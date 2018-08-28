import inspect
from typing import Tuple, Type, Union


def convert_exceptions(fn_or_none=None, *,
                       exc: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception,
                       to: Type[Exception] = RuntimeError):
    def decorator(fn):
        awaitable = inspect.iscoroutinefunction(fn) or inspect.isasyncgenfunction(fn)

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

        return sync_wrapper if not awaitable else async_wrapper

    return decorator(fn_or_none) if fn_or_none else decorator


_SENTINEL = object()


def default_on_error(fn_or_none=None, *,
                     exc: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception):
    def decorator(fn):
        awaitable = inspect.iscoroutinefunction(fn) or inspect.isasyncgenfunction(fn)

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

        return sync_wrapper if not awaitable else async_wrapper

    return decorator(fn_or_none) if fn_or_none else decorator
