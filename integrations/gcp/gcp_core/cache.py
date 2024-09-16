import functools
from port_ocean.context.event import event
from typing import Callable, Awaitable, Any
from port_ocean.utils.cache import hash_func

AsyncCallable = Callable[..., Awaitable[Any]]


def cache_coroutine_result() -> Callable[[AsyncCallable], AsyncCallable]:
    """Coroutine version of `cache_iterator_result` from port_ocean.utils.cache

    Decorator that caches the result of a coroutine function.
    It checks if the result is already in the cache, and if not,
    fetches the result, caches it, and returns the cached value.

    The cache is stored in the scope of the running event and is
    removed when the event is finished.

    Usage:
    ```python
    @cache_coroutine_result()
    async def my_coroutine_function():
        # Your code here
    ```
    """

    def decorator(func: AsyncCallable) -> AsyncCallable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            cache_key = hash_func(func.__name__, *args, **kwargs)

            if cache := event.attributes.get(cache_key):
                return cache

            result = await func(*args, **kwargs)
            event.attributes[cache_key] = result
            return result

        return wrapper

    return decorator
