from typing import Any
from port_ocean.core.models import Entity
from port_ocean.utils.failed_entity_handler import FailedEntityHandler
import pytest
from unittest.mock import MagicMock
from port_ocean.exceptions.core import (
    OceanAbortException,
)


def create_entity(
    identifier: str, buleprint: str, dependencies: dict[str, str] = {}
) -> Entity:
    entity = MagicMock()
    entity.identifier = identifier
    entity.blueprint = buleprint
    entity.relations = dependencies or {}
    return entity


processed_order: list[str] = []


async def mock_activate(entity: Any, _: Any, __: Any, **kwargs: Any) -> bool:
    processed_order.append(f"{entity.identifier}-{entity.blueprint}")
    return True


@pytest.mark.asyncio
async def test_handle_failed_with_dependencies() -> None:
    # processed_order:list[str] = []
    entity_a = create_entity(
        "entity_a",
        "buleprint_a",
    )  # No dependencies
    entity_b = create_entity(
        "entity_b", "buleprint_a", {"dep_name_1": "entity_a"}
    )  # Depends on entity_a
    entity_c = create_entity(
        "entity_c", "buleprint_b", {"dep_name_2": "entity_b"}
    )  # Depends on entity_b

    failed_entities_handler = FailedEntityHandler()
    # Register fails with unsorted order
    failed_entities_handler.register_failed_upsert_call_arguments(
        entity_c, MagicMock(), MagicMock(), mock_activate
    )
    failed_entities_handler.register_failed_upsert_call_arguments(
        entity_a, MagicMock(), MagicMock(), mock_activate
    )
    failed_entities_handler.register_failed_upsert_call_arguments(
        entity_b, MagicMock(), MagicMock(), mock_activate
    )

    await failed_entities_handler.handle_failed()
    assert processed_order == [
        "entity_a-buleprint_a",
        "entity_b-buleprint_a",
        "entity_c-buleprint_b",
    ], f"Processed order: {processed_order}"


@pytest.mark.asyncio
async def test_handle_failed_with_self_dependencies() -> None:
    entity_a = create_entity(
        "entity_a", "buleprint_a", {"dep_name_1": "entity_a"}
    )  # Self dependency
    entity_b = create_entity(
        "entity_b", "buleprint_a", {"dep_name_1": "entity_a"}
    )  # Depends on entity_a
    entity_c = create_entity(
        "entity_c", "buleprint_b", {"dep_name_2": "entity_b"}
    )  # Depends on entity_b

    failed_entities_handler = FailedEntityHandler()

    # Register fails with unsorted order
    failed_entities_handler.register_failed_upsert_call_arguments(
        entity_c, MagicMock(), MagicMock(), mock_activate
    )
    failed_entities_handler.register_failed_upsert_call_arguments(
        entity_a, MagicMock(), MagicMock(), mock_activate
    )
    failed_entities_handler.register_failed_upsert_call_arguments(
        entity_b, MagicMock(), MagicMock(), mock_activate
    )

    await failed_entities_handler.handle_failed()
    assert processed_order == [
        "entity_a-buleprint_a",
        "entity_b-buleprint_a",
        "entity_c-buleprint_b",
    ], f"Processed order: {processed_order}"


@pytest.mark.asyncio
async def test_handle_failed_with_circular_dependencies() -> None:
    # processed_order:list[str] = []
    entity_a = create_entity(
        "entity_a", "buleprint_a", {"dep_name_1": "entity_b"}
    )  # Self dependency
    entity_b = create_entity(
        "entity_b", "buleprint_a", {"dep_name_1": "entity_a"}
    )  # Depends on entity_a

    failed_entities_handler = FailedEntityHandler()
    try:
        failed_entities_handler.register_failed_upsert_call_arguments(
            entity_a, MagicMock(), MagicMock(), mock_activate
        )
        failed_entities_handler.register_failed_upsert_call_arguments(
            entity_b, MagicMock(), MagicMock(), mock_activate
        )
        await failed_entities_handler.handle_failed()

    except OceanAbortException as e:
        assert isinstance(e, OceanAbortException)
        assert (
            e.args[0]
            == "Cannot order entities due to cyclic dependencies. \nIf you do want to have cyclic dependencies, please make sure to set the keys 'createMissingRelatedEntities' and 'deleteDependentEntities' in the integration config in Port."
        )
