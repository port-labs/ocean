import functools
from port_ocean.context.event import event
import hashlib
from typing import Callable, Awaitable, Any

AsyncCallable = Callable[..., Awaitable[Any]]


def hash_func(function_name: str, *args: Any, **kwargs: Any) -> str:
    """
    Create a unique hash based on the function name, args, and kwargs.
    """
    args_str = str(args)
    kwargs_str = str(kwargs)
    concatenated_string = args_str + kwargs_str
    hash_object = hashlib.sha256(concatenated_string.encode())
    return f"{function_name}_{hash_object.hexdigest()}"


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
