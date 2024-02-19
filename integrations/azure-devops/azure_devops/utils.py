from enum import StrEnum
import functools
from port_ocean.context.event import event
from typing import Callable, Any, AsyncGenerator

class Kind(StrEnum):
    REPOSITORY = "repository"
    REPOSITORY_POLICY = "repository-policy"
    PULL_REQUEST = "pull-request"
    WORK_ITEM = "work-item"
    PIPELINE = "pipeline"
    BOARD = "board"
    MEMBER = "member"
    TEAM = "team"
    PROJECT = "project"


AsyncGeneratorCreatorType = Callable[..., AsyncGenerator[list[Any], None]]


def cache_results(
    cache_key: str,
) -> Callable[[AsyncGeneratorCreatorType], AsyncGeneratorCreatorType]:
    def decorator(method: AsyncGeneratorCreatorType) -> AsyncGeneratorCreatorType:
        @functools.wraps(method)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Check if the result is already in the cache
            if cache := event.attributes.get(cache_key):
                yield cache
                return

            # If not in cache, fetch the data
            cached_results = list()
            async for result in method(*args, **kwargs):
                cached_results.extend(result)
                yield result

            # Cache the results
            event.attributes[cache_key] = cached_results
            return

        return wrapper

    return decorator
