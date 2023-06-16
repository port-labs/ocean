from typing import List, TypeVar, Callable, Iterable, Union, Any

from port_ocean.core.handlers.manipulation.base import PortObjectDiff, Entity, Blueprint
from port_ocean.types import ObjectDiff


def is_valid_diff_item(item: Any) -> bool:
    return isinstance(item, list) and all([isinstance(i, dict) for i in item])


def validate_result(result: Any) -> ObjectDiff:
    if isinstance(result, dict):
        before = result.get("before", [])
        after = result.get("after", [])

        if is_valid_diff_item(before) and is_valid_diff_item(after):
            return {
                "after": after,
                "before": before,
            }
    raise Exception(f"Expected dict, got {type(result)} instead")


def is_same_entity(firs_entity: Entity, second_entity: Entity) -> bool:
    return (
        firs_entity.identifier == second_entity.identifier
        and firs_entity.blueprint == second_entity.blueprint
    )


def is_same_blueprint(firs_blueprint: Blueprint, second_blueprint: Blueprint) -> bool:
    return firs_blueprint.identifier == second_blueprint.identifier


T = TypeVar("T", bound=Union[Blueprint, Entity])


def get_unique(array: List[T], comparator: Callable[[T, T], bool]) -> List[T]:
    seen: List[T] = []
    result = []
    for item in array:
        if all(not comparator(item, seen_item) for seen_item in seen):
            seen.append(item)
            result.append(item)
    return result


def get_object_diff(
    before: Iterable[T], after: Iterable[T], comparator: Callable[[T, T], bool]
) -> PortObjectDiff[T]:
    return PortObjectDiff(
        deleted=get_unique(
            [
                item
                for item in before
                if not any(item == item_after for item_after in after)
            ],
            comparator,
        ),
        created=get_unique(
            [
                item
                for item in after
                if not any(item == item_before for item_before in before)
            ],
            comparator,
        ),
        modified=get_unique(
            [
                item
                for item in after
                if any(item == entity_before for entity_before in before)
            ],
            comparator,
        ),
    )
