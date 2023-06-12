from typing import List, Set, TypeVar, Callable, Iterable, Union

from port_ocean.core.handlers.manipulation.base import PortObjectDiff
from port_ocean.models.port import Entity, Blueprint


def is_same_entity(firs_entity: Entity, second_entity: Entity) -> bool:
    return (
        firs_entity.identifier == second_entity.identifier
        and firs_entity.blueprint == second_entity.blueprint
    )


def is_same_blueprint(firs_blueprint: Blueprint, second_blueprint: Blueprint) -> bool:
    return firs_blueprint.identifier == second_blueprint.identifier


T = TypeVar("T", bound=Union[Blueprint, Entity])


def get_unique(array: List[T], comparator: Callable[[T, T], bool]) -> List[T]:
    seen: Set[T] = set()
    result = []
    for item in array:
        if all(not comparator(item, seen_item) for seen_item in seen):
            seen.add(item)
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
