import functools
from typing import Callable, AsyncIterator, Any

from port_ocean.context.event import event

AsyncIteratorCallable = Callable[..., AsyncIterator[list[Any]]]


def cache_iterator_result(
    cache_key: str,
) -> Callable[[AsyncIteratorCallable], AsyncIteratorCallable]:
    """
    This decorator caches the results of an async iterator function. It checks if the result is already in the cache
    and if not, it fetches the all the data and caches it at ocean.attributes cache the end of the iteration.

    The cache will be stored in the scope of the running event and will be removed when the event is finished.

    For example, you can use this to cache data coming back from the third-party API to avoid making the same request
    multiple times for each kind.

    Usage:
    ```python
    @cache_iterator_result("my_cache_key")
    async def my_async_iterator_function():
        # Your code here
    ```
    """

    def decorator(func: AsyncIteratorCallable) -> AsyncIteratorCallable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Check if the result is already in the cache
            if cache := event.attributes.get(cache_key):
                yield cache
                return

            # If not in cache, fetch the data
            cached_results = list()
            async for result in func(*args, **kwargs):
                cached_results.extend(result)
                yield result

            # Cache the results
            event.attributes[cache_key] = cached_results
            return

        return wrapper

    return decorator
