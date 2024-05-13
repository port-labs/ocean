from typing import Iterable, Any, TypeVar

from pydantic import parse_obj_as, ValidationError

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


def get_port_diff(
    before: Iterable[Entity],
    after: Iterable[Entity],
) -> EntityPortDiff:
    before_dict = {}
    after_dict = {}
    created = []
    modified = []
    deleted = []

    # Create dictionaries for before and after lists
    for entity in before:
        key = (entity.identifier, entity.blueprint)
        before_dict[key] = entity

    for entity in after:
        key = (entity.identifier, entity.blueprint)
        after_dict[key] = entity

    # Find created, modified, and deleted objects
    for key, obj in after_dict.items():
        if key not in before_dict:
            created.append(obj)
        else:
            modified.append(obj)

    for key, obj in before_dict.items():
        if key not in after_dict:
            deleted.append(obj)

    return EntityPortDiff(created=created, modified=modified, deleted=deleted)
