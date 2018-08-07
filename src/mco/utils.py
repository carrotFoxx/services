import inspect
from typing import Type


def convert_exceptions(fn_or_none=None, *,
                       exc: Type[Exception] = Exception,
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
