import functools
import hashlib
from typing import Callable, AsyncIterator, Awaitable, Any
from port_ocean.context.event import event
from loguru import logger
from typing import Dict, Set, List

AsyncIteratorCallable = Callable[..., AsyncIterator[list[Any]]]
AsyncCallable = Callable[..., Awaitable[Any]]


def hash_func(function_name: str, *args: Any, **kwargs: Any) -> str:
    args_str = str(args)
    kwargs_str = str(kwargs)
    concatenated_string = args_str + kwargs_str
    hash_object = hashlib.sha256(concatenated_string.encode())
    return f"{function_name}_{hash_object.hexdigest()}"


def cache_iterator_result() -> Callable[[AsyncIteratorCallable], AsyncIteratorCallable]:
    """
    This decorator caches the results of an async iterator function. It checks if the result is already in the cache
    and if not, it fetches the all the data and caches it at ocean.attributes cache the end of the iteration.

    The cache will be stored in the scope of the running event and will be removed when the event is finished.

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
            # Create Hash key from function name, args and kwargs
            cache_key = hash_func(func.__name__, *args, **kwargs)

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


class CacheDependencyGraph:
    """
    A dependency graph for controlling which resources
    or functions get cached based on selected and declared dependencies.

    * Each 'node' is just a string ID (e.g. "TEAM", "PROJECT", "ISSUE").
    * If X depends on Y, that means enabling X automatically enables Y.

    This class also includes a 'prune_unnecessary()' routine that removes
    any resource requested alone but is not actually used by another
    (i.e. no child depends on it).
    """

    def __init__(self) -> None:
        # Example: dependencies["MEMBERS"] = {"TEAM"}
        self.dependencies: Dict[str, Set[str]] = {}
        self.active: Set[str] = set()

    def register(self, resource_name: str, depends_on: List[str] = None) -> None:
        """
        Registers a resource with zero or more dependencies.
        For example:
          register("MEMBERS", depends_on=["TEAM"])
          register("TEAM")  # no dependencies
        """
        self.dependencies[resource_name] = set(depends_on or [])

    def compute_active(self, requested: List[str]) -> None:
        """
        1) Clears self.active
        2) Recursively marks all requested items and their dependencies as 'active'.
        3) Prunes resources that are explicitly requested alone, but aren't
           actually needed by any child resource in the graph.

        After calling this, self.active will contain the final set of resources
        that are 'truly' needed (and hence should be cached).
        """
        self.active.clear()

        # Gather all requested items (plus their dependencies)
        for item in requested:
            self._collect(item)

        # Now remove resources if they are requested alone and do not
        # have a 'child' also in active. We'll do it iteratively in case
        # one removal triggers others.
        self._prune_unnecessary(requested)

    def _collect(self, item: str) -> None:
        """Depth-first search to add item + all dependencies to active."""
        if item not in self.active:
            self.active.add(item)
            for dep in self.dependencies.get(item, []):
                self._collect(dep)

    def _prune_unnecessary(self, requested: List[str]) -> None:
        """Prune resources that are requested alone but have no active dependents.
        Remove from the active set any resource that:
             1) Was directly requested,
             2) Has no children (no resources in the graph that depend on it)
                 which are also in the active set.

             We do this in a loop until no more changes occur,
             in case there's a cascading effect.
        """
        requested_set = set(requested)

        while True:
            to_prune = {
                resource
                for resource in self.active
                if resource in requested_set
                and not any(
                    resource in deps and r in self.active
                    for r, deps in self.dependencies.items()
                )
            }

            if not to_prune:
                break

            self.active -= to_prune
            logger.debug(
                f"Pruning {to_prune} from active set; no active child depends on them."
            )

    def is_active(self, resource_name: str) -> bool:
        """
        Returns True if 'resource_name' ended up in the final active set.
        """
        return resource_name in self.active


def conditional_cache_iterator_result(
    graph: CacheDependencyGraph, resource_name: str
) -> Callable[[AsyncIteratorCallable], AsyncIteratorCallable]:
    """
    Decorator that conditionally applies caching to an async-iterator function
    IFF 'resource_name' is active in the graph. If it's not active, yields raw data.

    Example:
      @conditional_cache_iterator_result(graph, "TEAM")
      async def fetch_teams(...):
          ...
    """

    def decorator(func: AsyncIteratorCallable) -> AsyncIteratorCallable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not graph.is_active(resource_name):
                async for batch in func(*args, **kwargs):
                    yield batch
                return

            # Resource is active -> do caching
            cache_key = hash_func(func.__name__, *args, **kwargs)
            if cache := event.attributes.get(cache_key):
                yield cache
                return

            all_items: List[Any] = []
            async for batch in func(*args, **kwargs):
                all_items.extend(batch)
                yield batch

            event.attributes[cache_key] = all_items

        return wrapper

    return decorator


def conditional_cache_coroutine_result(
    graph: CacheDependencyGraph, resource_name: str
) -> Callable[[AsyncCallable], AsyncCallable]:
    """
    Decorator that conditionally applies caching to a single-return async function
    if 'resource_name' is active in the graph. Otherwise calls the function directly.
    """

    def decorator(func: AsyncCallable) -> AsyncCallable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not graph.is_active(resource_name):
                return await func(*args, **kwargs)

            cache_key = hash_func(func.__name__, *args, **kwargs)
            if cache := event.attributes.get(cache_key):
                return cache
            result = await func(*args, **kwargs)
            event.attributes[cache_key] = result
            return result

        return wrapper

    return decorator
