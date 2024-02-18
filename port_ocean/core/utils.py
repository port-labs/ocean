import functools
from typing import AsyncGenerator, Callable, Iterable, Any, TypeVar

from pydantic import parse_obj_as, ValidationError
from port_ocean.context.event import event

from port_ocean.core.handlers.entity_processor.base import EntityPortDiff
from port_ocean.core.models import Entity
from port_ocean.core.ocean_types import RAW_RESULT
from port_ocean.exceptions.core import RawObjectValidationException

T = TypeVar("T", bound=tuple[list[Any], ...])


def zip_and_sum(collection: Iterable[T]) -> T:
    return tuple(sum(items, []) for items in zip(*collection))  # type: ignore


def validate_result(result: Any) -> RAW_RESULT:
    try:
        return parse_obj_as(list[dict[str, Any]], result)
    except ValidationError as e:
        raise RawObjectValidationException(f"Expected list[dict[str, Any]], Error: {e}")


def is_same_entity(first_entity: Entity, second_entity: Entity) -> bool:
    return (
        first_entity.identifier == second_entity.identifier
        and first_entity.blueprint == second_entity.blueprint
    )


def get_unique(array: list[Entity]) -> list[Entity]:
    result: list[Entity] = []
    for item in array:
        if all(not is_same_entity(item, seen_item) for seen_item in result):
            result.append(item)
    return result


def get_port_diff(
    before: Iterable[Entity],
    after: Iterable[Entity],
) -> EntityPortDiff:
    return EntityPortDiff(
        deleted=get_unique(
            [
                item
                for item in before
                if not any(is_same_entity(item, item_after) for item_after in after)
            ],
        ),
        created=get_unique(
            [
                item
                for item in after
                if not any(is_same_entity(item, item_before) for item_before in before)
            ],
        ),
        modified=get_unique(
            [
                item
                for item in after
                if any(is_same_entity(item, item_before) for item_before in before)
            ],
        ),
    )


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
