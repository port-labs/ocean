import asyncio
import hashlib
import json
from typing import Iterable, Any, TypeVar, Callable, Awaitable

from loguru import logger
from pydantic import parse_obj_as, ValidationError


from port_ocean.clients.port.client import PortClient
from port_ocean.core.models import Entity, Runtime
from port_ocean.core.models import EntityPortDiff
from port_ocean.core.ocean_types import RAW_RESULT
from port_ocean.exceptions.core import (
    RawObjectValidationException,
    IntegrationRuntimeException,
)

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


async def validate_integration_runtime(
    port_client: PortClient,
    requested_runtime: Runtime,
) -> None:
    logger.debug("Validating integration runtime")
    current_integration = await port_client.get_current_integration(
        should_raise=False, should_log=False
    )
    current_installation_type = current_integration.get("installationType", "OnPrem")
    if current_integration and not requested_runtime.is_installation_type_compatible(
        current_installation_type
    ):
        raise IntegrationRuntimeException(
            f"Invalid Runtime! Requested to run existing {current_installation_type} integration in {requested_runtime} runtime."
        )


Q = TypeVar("Q")


async def gather_and_split_errors_from_results(
    task: Iterable[Awaitable[Q]],
    result_threshold_validation: Callable[[Q | Exception], bool] | None = None,
) -> tuple[list[Q], list[Exception]]:
    valid_items: list[Q] = []
    errors: list[Exception] = []
    results = await asyncio.gather(*task, return_exceptions=True)
    for item in results:
        # return_exceptions will also catch Python BaseException which also includes KeyboardInterrupt, SystemExit, GeneratorExit
        # https://docs.python.org/3/library/asyncio-task.html#asyncio.gather
        # These exceptions should be raised and not caught for the application to exit properly.
        # https://stackoverflow.com/a/17802352
        if isinstance(item, BaseException) and not isinstance(item, Exception):
            raise item
        elif isinstance(item, Exception):
            errors.append(item)
        elif not result_threshold_validation or result_threshold_validation(item):
            valid_items.append(item)

    return valid_items, errors


def get_port_diff(before: Iterable[Entity], after: Iterable[Entity]) -> EntityPortDiff:
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


def are_teams_different(
    first_team: str | None | list[Any] | dict[str, Any],
    second_team: str | None | list[Any] | dict[str, Any],
) -> bool:
    if isinstance(first_team, list) and isinstance(second_team, list):
        return sorted(first_team) != sorted(second_team)
    return first_team != second_team


def are_entities_fields_equal(
    first_entity_field: dict[str, Any], second_entity_field: dict[str, Any]
) -> bool:
    """
    Compare two entity fields by serializing them to JSON and comparing their SHA-256 hashes.
    Removes keys with None values before comparison if the corresponding key doesn't exist in the other dict.

    Args:
        first_entity_field: First entity field dictionary to compare
        second_entity_field: Second entity field dictionary to compare

    Returns:
        bool: True if the entity fields have identical content
    """
    first_entity_field_copy = first_entity_field.copy()

    for key in list(first_entity_field.keys()):
        if first_entity_field[key] is None and key not in second_entity_field:
            del first_entity_field_copy[key]

    first_props = json.dumps(first_entity_field_copy, sort_keys=True)
    second_props = json.dumps(second_entity_field, sort_keys=True)
    first_hash = hashlib.sha256(first_props.encode()).hexdigest()
    second_hash = hashlib.sha256(second_props.encode()).hexdigest()
    return first_hash == second_hash


def are_entities_different(first_entity: Entity, second_entity: Entity) -> bool:
    if first_entity.title != second_entity.title:
        return True
    if are_teams_different(first_entity.team, second_entity.team):
        return True
    if not are_entities_fields_equal(first_entity.properties, second_entity.properties):
        return True
    if not are_entities_fields_equal(first_entity.relations, second_entity.relations):
        return True

    return False


def resolve_entities_diff(
    source_entities: list[Entity], target_entities: list[Entity]
) -> list[Entity]:
    """
    Maps the entities into filtered list of source entities, excluding matches found in target that needs to be upserted
    Args:
        source_entities: List of entities from third party source
        target_entities: List of existing Port entities

    Returns:
        list[Entity]: Filtered list of source entities, excluding matches found in target
    """
    target_entities_dict = {}
    source_entities_dict = {}
    changed_entities = []

    for entity in target_entities:
        key = (entity.identifier, entity.blueprint)
        target_entities_dict[key] = entity

    for entity in source_entities:
        if entity.is_using_search_identifier or entity.is_using_search_relation:
            return source_entities
        key = (entity.identifier, entity.blueprint)
        source_entities_dict[key] = entity

        entity_at_target = target_entities_dict.get(key, None)
        if entity_at_target is None:
            changed_entities.append(entity)
        elif are_entities_different(entity, target_entities_dict[key]):
            changed_entities.append(entity)

    return changed_entities
