import pytest
from unittest.mock import  MagicMock
from port_ocean.context.event import event, event_context, EventType
from port_ocean.exceptions.core import (
    OceanAbortException,
)
from typing import Any

def create_entity(identifier:str,buleprint:str, dependencies:dict[str,str]=None):
    entity = MagicMock()
    entity.identifier = identifier
    entity.blueprint = buleprint
    entity.relations = dependencies or {}
    return entity

async def mock_activate(processed_order:list[str],entity:MagicMock):
    processed_order.append(f"{entity.identifier}-{entity.blueprint}")
    return True

@pytest.mark.asyncio
async def test_handle_failed_with_dependencies():
    processed_order:list[str] = []
    entity_a = create_entity("entity_a", "buleprint_a",)  # No dependencies
    entity_b = create_entity("entity_b", "buleprint_a", {"dep_name_1":"entity_a"})  # Depends on entity_a
    entity_c = create_entity("entity_c", "buleprint_b", {"dep_name_2":"entity_b"})  # Depends on entity_b


    async with event_context(EventType.RESYNC, "manual"):
        # Register fails with unsorted order
        event.register_failed_upsert_call_arguments(entity_c, lambda: mock_activate(processed_order,entity_c))
        event.register_failed_upsert_call_arguments(entity_a, lambda: mock_activate(processed_order,entity_a))
        event.register_failed_upsert_call_arguments(entity_b, lambda: mock_activate(processed_order,entity_b))

        await event.handle_failed()

    assert processed_order == ["entity_a-buleprint_a", "entity_b-buleprint_a", "entity_c-buleprint_b"], f"Processed order: {processed_order}"

@pytest.mark.asyncio
async def test_handle_failed_with_self_dependencies():
    processed_order:list[str] = []
    entity_a = create_entity("entity_a", "buleprint_a",{"dep_name_1":"entity_a"})  # Self dependency
    entity_b = create_entity("entity_b", "buleprint_a", {"dep_name_1":"entity_a"})  # Depends on entity_a
    entity_c = create_entity("entity_c", "buleprint_b", {"dep_name_2":"entity_b"})  # Depends on entity_b


    async with event_context(EventType.RESYNC, "manual"):
        # Register fails with unsorted order
        event.register_failed_upsert_call_arguments(entity_c, lambda: mock_activate(processed_order,entity_c))
        event.register_failed_upsert_call_arguments(entity_a, lambda: mock_activate(processed_order,entity_a))
        event.register_failed_upsert_call_arguments(entity_b, lambda: mock_activate(processed_order,entity_b))

        await event.handle_failed()

    assert processed_order == ["entity_a-buleprint_a", "entity_b-buleprint_a", "entity_c-buleprint_b"], f"Processed order: {processed_order}"

@pytest.mark.asyncio
async def test_handle_failed_with_circular_dependencies():
    processed_order:list[str] = []
    entity_a = create_entity("entity_a", "buleprint_a",{"dep_name_1":"entity_b"})  # Self dependency
    entity_b = create_entity("entity_b", "buleprint_a", {"dep_name_1":"entity_a"})  # Depends on entity_a

    try:
        async with event_context(EventType.RESYNC, "manual"):
            # Register fails with unsorted order
            event.register_failed_upsert_call_arguments(entity_a, lambda: mock_activate(processed_order,entity_a))
            event.register_failed_upsert_call_arguments(entity_b, lambda: mock_activate(processed_order,entity_b))
            await event.handle_failed()
    except OceanAbortException as e:
        assert isinstance(e,OceanAbortException)
        assert e.args[0] == "Cannot order entities due to cyclic dependencies. \nIf you do want to have cyclic dependencies, please make sure to set the keys 'createMissingRelatedEntities' and 'deleteDependentEntities' in the integration config in Port."
