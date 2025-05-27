import functools
import hashlib
import base64
from typing import Callable, AsyncIterator, Awaitable, Any
from port_ocean.cache.errors import FailedToReadCacheError, FailedToWriteCacheError
from port_ocean.context.ocean import ocean
from loguru import logger

AsyncIteratorCallable = Callable[..., AsyncIterator[list[Any]]]
AsyncCallable = Callable[..., Awaitable[Any]]


def hash_func(function_name: str, *args: Any, **kwargs: Any) -> str:
    args_str = str(args)
    kwargs_str = str(kwargs)
    concatenated_string = args_str + kwargs_str
    hash_object = hashlib.sha256(concatenated_string.encode())
    short_hash = base64.urlsafe_b64encode(hash_object.digest()[:8]).decode("ascii")
    short_hash = short_hash.rstrip("=").replace("-", "_").replace("+", "_")
    return f"{function_name}_{short_hash}"


def cache_iterator_result() -> Callable[[AsyncIteratorCallable], AsyncIteratorCallable]:
    """
    This decorator caches the results of an async iterator function. It checks if the result is already in the cache
    and if not, it fetches the all the data and caches it at the end of the iteration.

    The cache will be stored in the scope of the running event and will be removed when the event is finished.
    If a database is configured, the cache will also be stored in the database.

    For example, you can use this to cache data coming back from the third-party API to avoid making the same request
    multiple times for each kind.

    The caching mechanism also detects changes in parameters.
    If a function is called with different parameter values, it will be stored in different hash keys for each unique call.

    Usage:
    ```python
    @cache_iterator_result()
    async def my_async_iterator_function():
        # Your code here
    ```
    """

    def decorator(func: AsyncIteratorCallable) -> AsyncIteratorCallable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            cache_key = hash_func(func.__name__, *args, **kwargs)

            # Check if the result is already in the cache
            try:
                if cache := await ocean.app.cache_provider.get(cache_key):
                    yield cache
                    return
            except FailedToReadCacheError as e:
                logger.warning(f"Failed to read cache for {cache_key}: {str(e)}")

            # If not in cache, fetch the data
            cached_results = list()
            async for result in func(*args, **kwargs):
                cached_results.extend(result)
                yield result

            # Cache the results
            try:
                await ocean.app.cache_provider.set(
                    cache_key,
                    cached_results,
                )
            except FailedToWriteCacheError as e:
                logger.warning(f"Failed to write cache for {cache_key}: {str(e)}")
            return

        return wrapper

    return decorator


def cache_coroutine_result() -> Callable[[AsyncCallable], AsyncCallable]:
    """Coroutine version of `cache_iterator_result` from port_ocean.utils.cache

    Decorator that caches the result of a coroutine function.
    It checks if the result is already in the cache, and if not,
    fetches the result, caches it, and returns the cached value.

    The cache is stored in the scope of the running event and is
    removed when the event is finished.
    If a database is configured, the cache will also be stored in the database.

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
            try:
                if cache := await ocean.app.cache_provider.get(cache_key):
                    return cache
            except FailedToReadCacheError as e:
                logger.warning(f"Failed to read cache for {cache_key}: {str(e)}")

            result = await func(*args, **kwargs)
            try:
                await ocean.app.cache_provider.set(
                    cache_key,
                    result,
                )
            except FailedToWriteCacheError as e:
                logger.warning(f"Failed to write cache for {cache_key}: {str(e)}")
            return result

        return wrapper

    return decorator
