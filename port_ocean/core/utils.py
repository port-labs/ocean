from typing import List, TypeVar, Callable, Iterable, Union, Any, Dict

from port_ocean.core.handlers.manipulation.base import PortDiff
from port_ocean.core.models import Entity, Blueprint
from port_ocean.types import RawObjectDiff


def is_valid_diff_item(item: Any) -> bool:
    return isinstance(item, list) and all([isinstance(i, dict) for i in item] or [True])


def validate_result(result: Any) -> List[Dict[Any, Any]]:
    if isinstance(result, list):
        if is_valid_diff_item(result):
            return result
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


def get_port_diff(
    before: Iterable[T], after: Iterable[T], comparator: Callable[[T, T], bool]
) -> PortDiff[T]:
    return PortDiff(
        deleted=get_unique(
            [
                item
                for item in before
                if not any(comparator(item, item_after) for item_after in after)
            ],
            comparator,
        ),
        created=get_unique(
            [
                item
                for item in after
                if not any(comparator(item, item_before) for item_before in before)
            ],
            comparator,
        ),
        modified=get_unique(
            [
                item
                for item in after
                if any(comparator(item, entity_before) for entity_before in before)
            ],
            comparator,
        ),
    )
