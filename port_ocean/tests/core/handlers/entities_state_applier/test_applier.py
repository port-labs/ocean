from unittest.mock import Mock, patch
import pytest
from port_ocean.core.handlers.entities_state_applier.port.applier import (
    HttpEntitiesStateApplier,
)
from port_ocean.core.models import Entity
from port_ocean.core.ocean_types import EntityDiff
from port_ocean.clients.port.types import UserAgentType
from port_ocean.ocean import Ocean
from port_ocean.context.ocean import PortOceanContext
from port_ocean.tests.core.conftest import create_entity
from port_ocean.core.handlers.port_app_config.models import PortAppConfig
from port_ocean.context.event import event_context, EventType


@pytest.mark.asyncio
async def test_delete_diff_no_deleted_entities() -> None:
    applier = HttpEntitiesStateApplier(Mock())
    entities = EntityDiff(
        before=[Entity(identifier="1", blueprint="test")],
        after=[Entity(identifier="1", blueprint="test")],
    )

    with patch.object(applier, "_safe_delete") as mock_safe_delete:
        await applier.delete_diff(entities, UserAgentType.exporter)

    mock_safe_delete.assert_not_called()


@pytest.mark.asyncio
async def test_delete_diff_below_threshold(mock_context: PortOceanContext) -> None:
    applier = HttpEntitiesStateApplier(mock_context)
    entities = EntityDiff(
        before=[
            Entity(identifier="1", blueprint="test"),
            Entity(identifier="2", blueprint="test"),
            Entity(identifier="3", blueprint="test"),
        ],
        after=[
            Entity(identifier="1", blueprint="test"),
            Entity(identifier="2", blueprint="test"),
        ],
    )

    with patch.object(applier, "_safe_delete") as mock_safe_delete:
        await applier.delete_diff(
            entities, UserAgentType.exporter, entity_deletion_threshold=0.9
        )

    mock_safe_delete.assert_called_once()
    assert len(mock_safe_delete.call_args[0][0]) == 1
    assert mock_safe_delete.call_args[0][0][0].identifier == "3"


@pytest.mark.asyncio
async def test_delete_diff_above_default_threshold(
    mock_context: PortOceanContext,
) -> None:
    applier = HttpEntitiesStateApplier(mock_context)
    entities = EntityDiff(
        before=[
            Entity(identifier="1", blueprint="test"),
            Entity(identifier="2", blueprint="test"),
            Entity(identifier="3", blueprint="test"),
        ],
        after=[],
    )

    with patch.object(applier, "_safe_delete") as mock_safe_delete:
        await applier.delete_diff(
            entities, UserAgentType.exporter, entity_deletion_threshold=0.9
        )

    mock_safe_delete.assert_not_called()


@pytest.mark.asyncio
async def test_delete_diff_custom_threshold_above_threshold_not_deleted(
    mock_context: PortOceanContext,
) -> None:
    applier = HttpEntitiesStateApplier(mock_context)
    entities = EntityDiff(
        before=[
            Entity(identifier="1", blueprint="test"),
            Entity(identifier="2", blueprint="test"),
        ],
        after=[],
    )

    with patch.object(applier, "_safe_delete") as mock_safe_delete:
        await applier.delete_diff(
            entities, UserAgentType.exporter, entity_deletion_threshold=0.5
        )

    mock_safe_delete.assert_not_called()


@pytest.mark.asyncio
async def test_delete_diff_custom_threshold_0_not_deleted(
    mock_context: PortOceanContext,
) -> None:
    applier = HttpEntitiesStateApplier(mock_context)
    entities = EntityDiff(
        before=[
            Entity(identifier="1", blueprint="test"),
            Entity(identifier="2", blueprint="test"),
        ],
        after=[
            Entity(identifier="2", blueprint="test"),
            Entity(identifier="3", blueprint="test"),
        ],
    )

    with patch.object(applier, "_safe_delete") as mock_safe_delete:
        await applier.delete_diff(
            entities, UserAgentType.exporter, entity_deletion_threshold=0
        )

    mock_safe_delete.assert_not_called()


@pytest.mark.asyncio
async def test_applier_with_mock_context(
    mock_ocean: Ocean,
    mock_context: PortOceanContext,
    mock_port_app_config: PortAppConfig,
) -> None:
    # Create an applier using the mock_context fixture
    applier = HttpEntitiesStateApplier(mock_context)

    # Create test entities
    entity = Entity(identifier="test_entity", blueprint="test_blueprint")

    async with event_context(EventType.RESYNC, trigger_type="machine") as event:
        event.port_app_config = mock_port_app_config

        # Test the upsert method with mocked client
        with patch.object(mock_ocean.port_client.client, "post") as mock_post:
            mock_post.return_value = Mock(
                status_code=200,
                json=lambda: {
                    "entity": {
                        "identifier": "test_entity",
                        "blueprint": "test_blueprint",
                    }
                },
            )

            result = await applier.upsert([entity], UserAgentType.exporter)

            # Assert that the post method was called
            mock_post.assert_called_once()
            assert len(result) == 1
            assert result[0].identifier == "test_entity"


@pytest.mark.asyncio
async def test_applier_one_not_upserted(
    mock_ocean: Ocean,
    mock_context: PortOceanContext,
    mock_port_app_config: PortAppConfig,
) -> None:
    # Create an applier using the mock_context fixture
    applier = HttpEntitiesStateApplier(mock_context)

    # Create test entities
    entity = Entity(identifier="test_entity", blueprint="test_blueprint")

    async with event_context(EventType.RESYNC, trigger_type="machine") as event:
        # Mock the register_entity method
        event.entity_topological_sorter.register_entity = Mock()  # type: ignore
        event.port_app_config = mock_port_app_config

        # Test the upsert method with mocked client
        with patch.object(mock_ocean.port_client.client, "post") as mock_post:
            mock_post.return_value = Mock(
                status_code=404,
                json=lambda: {"ok": False, "error": "not_found"},
            )

            result = await applier.upsert([entity], UserAgentType.exporter)

            # Assert that the post method was called
            mock_post.assert_called_once()
            assert len(result) == 0
            event.entity_topological_sorter.register_entity.assert_called_once_with(
                entity
            )


@pytest.mark.asyncio
async def test_applier_error_upserting(
    mock_ocean: Ocean,
    mock_context: PortOceanContext,
    mock_port_app_config: PortAppConfig,
) -> None:
    # Create an applier using the mock_context fixture
    applier = HttpEntitiesStateApplier(mock_context)

    # Create test entities
    entity = Entity(identifier="test_entity", blueprint="test_blueprint")

    async with event_context(EventType.RESYNC, trigger_type="machine") as event:
        # Mock the register_entity method
        event.entity_topological_sorter.register_entity = Mock()  # type: ignore
        event.port_app_config = mock_port_app_config

        # Test the upsert method with mocked client
        with patch.object(mock_ocean.port_client.client, "post") as mock_post:
            mock_post.return_value = Mock(
                status_code=404,
                json=lambda: {"ok": False, "error": "not_found"},
            )

            result = await applier.upsert([entity], UserAgentType.exporter)

            # Assert that the post method was called
            mock_post.assert_called_once()
            assert len(result) == 0
            event.entity_topological_sorter.register_entity.assert_called_once_with(
                entity
            )


@pytest.mark.asyncio
async def test_using_create_entity_helper(
    mock_ocean: Ocean,
    mock_context: PortOceanContext,
    mock_port_app_config: PortAppConfig,
) -> None:
    # Create the applier with the mock context
    applier = HttpEntitiesStateApplier(mock_context)

    # Create test entities using the helper function
    entity1 = create_entity("entity1", "service", {"related_to": "entity2"}, False)

    # Test that entities were created correctly
    assert entity1.identifier == "entity1"
    assert entity1.blueprint == "service"
    assert entity1.relations == {"related_to": "entity2"}
    assert entity1.properties == {"mock_is_to_fail": False}

    # Test the applier with these entities
    async with event_context(EventType.RESYNC, trigger_type="machine") as event:
        event.port_app_config = mock_port_app_config

        with patch.object(mock_ocean.port_client.client, "post") as mock_post:
            mock_post.return_value = Mock(
                status_code=200,
                json=lambda: {
                    "entity": {"identifier": "entity1", "blueprint": "service"}
                },
            )

            result = await applier.upsert([entity1], UserAgentType.exporter)

            mock_post.assert_called_once()
            assert len(result) == 1
