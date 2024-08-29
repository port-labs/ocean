import asyncio
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
    current_runtime = current_integration.get("installationType", "OnPrem")
    if current_integration and current_runtime != requested_runtime.value:
        raise IntegrationRuntimeException(
            f"Invalid Runtime! Requested to run existing {current_runtime} integration in {requested_runtime} runtime."
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
