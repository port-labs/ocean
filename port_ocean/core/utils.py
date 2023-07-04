from typing import Iterable, Any, TypeVar

from pydantic import parse_obj_as, ValidationError

from port_ocean.core.handlers.manipulation.base import EntityPortDiff
from port_ocean.core.models import Entity
from port_ocean.exceptions.core import RawObjectValidationException


def validate_result(result: Any) -> list[dict[str, Any]]:
    try:
        return parse_obj_as(list[dict[str, Any]], result)
    except ValidationError as e:
        raise RawObjectValidationException(f"Expected list[dict[str, Any]], Error: {e}")


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
