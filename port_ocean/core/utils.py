from typing import Iterable, Any, TypeVar

from port_ocean.core.handlers.manipulation.base import EntityPortDiff
from port_ocean.core.models import Entity


def is_valid_diff_item(item: Any) -> bool:
    return isinstance(item, list) and all([isinstance(i, dict) for i in item] or [True])


def validate_result(result: Any) -> list[dict[Any, Any]]:
    if isinstance(result, list):
        if is_valid_diff_item(result):
            return result
    raise Exception(f"Expected dict, got {type(result)} instead")


def is_same_entity(firs_entity: Entity, second_entity: Entity) -> bool:
    return (
        firs_entity.identifier == second_entity.identifier
        and firs_entity.blueprint == second_entity.blueprint
    )


def get_unique(array: list[Entity]) -> list[Entity]:
    seen: list[Entity] = []
    result = []
    for item in array:
        if all(not is_same_entity(item, seen_item) for seen_item in seen):
            seen.append(item)
            result.append(item)
    return result


T = TypeVar("T", bound=list[Any])


def zip_and_sum(collection: Iterable[tuple[T, ...]]) -> tuple[T, ...]:
    return tuple(sum(items, []) for items in zip(*collection))  # type: ignore


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
                if any(is_same_entity(item, entity_before) for entity_before in before)
            ],
        ),
    )
