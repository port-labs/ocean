import functools
from typing import Callable, AsyncIterator, Any

from port_ocean.context.event import event

AsyncIteratorCallable = Callable[..., AsyncIterator[list[Any]]]


def cache_iterator_result(
    cache_key: str,
) -> Callable[[AsyncIteratorCallable], AsyncIteratorCallable]:
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
