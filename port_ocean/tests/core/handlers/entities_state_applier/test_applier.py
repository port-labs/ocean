from unittest.mock import Mock, patch, AsyncMock
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
async def test_delete_diff_no_deleted_entities(mock_context: PortOceanContext) -> None:
    applier = HttpEntitiesStateApplier(mock_context)
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
    applier = HttpEntitiesStateApplier(mock_context)
    entity = Entity(identifier="test_entity", blueprint="test_blueprint")

    async with event_context(EventType.RESYNC, trigger_type="machine") as event:
        event.port_app_config = mock_port_app_config
        event.entity_topological_sorter = Mock()

        mock_blueprint = Mock()
        mock_blueprint.identifier = "test_blueprint"
        mock_blueprint.relations = {}
        mock_get_blueprint = AsyncMock(return_value=mock_blueprint)
        setattr(mock_ocean.port_client, "get_blueprint", mock_get_blueprint)

        mock_ocean.config.upsert_entities_batch_max_length = 100
        mock_ocean.config.upsert_entities_batch_max_size_in_bytes = 1000

        mock_upsert = AsyncMock(return_value=[(True, entity)])
        setattr(mock_ocean.port_client, "upsert_entities_bulk", mock_upsert)

        result = await applier.upsert([entity], UserAgentType.exporter)
        mock_upsert.assert_called_once()
        assert len(result) == 1
        assert result[0].identifier == "test_entity"


@pytest.mark.asyncio
async def test_applier_one_not_upserted(
    mock_ocean: Ocean,
    mock_context: PortOceanContext,
    mock_port_app_config: PortAppConfig,
) -> None:
    applier = HttpEntitiesStateApplier(mock_context)
    entity = Entity(identifier="test_entity", blueprint="test_blueprint")

    async with event_context(EventType.RESYNC, trigger_type="machine") as event:
        event.entity_topological_sorter.register_entity = Mock()  # type: ignore
        event.port_app_config = mock_port_app_config

        mock_ocean.config.upsert_entities_batch_max_length = 100
        mock_ocean.config.upsert_entities_batch_max_size_in_bytes = 1000

        mock_upsert = AsyncMock(return_value=[(False, entity)])
        setattr(mock_ocean.port_client, "upsert_entities_bulk", mock_upsert)

        result = await applier.upsert([entity], UserAgentType.exporter)

        mock_upsert.assert_called_once()
        assert len(result) == 0
        event.entity_topological_sorter.register_entity.assert_called_once_with(entity)


@pytest.mark.asyncio
async def test_applier_error_upserting(
    mock_ocean: Ocean,
    mock_context: PortOceanContext,
    mock_port_app_config: PortAppConfig,
) -> None:
    applier = HttpEntitiesStateApplier(mock_context)
    entity = Entity(identifier="test_entity", blueprint="test_blueprint")

    async with event_context(EventType.RESYNC, trigger_type="machine") as event:
        event.entity_topological_sorter.register_entity = Mock()  # type: ignore
        event.port_app_config = mock_port_app_config

        mock_ocean.config.upsert_entities_batch_max_length = 100
        mock_ocean.config.upsert_entities_batch_max_size_in_bytes = 1000

        mock_upsert = AsyncMock(return_value=[(False, entity)])
        setattr(mock_ocean.port_client, "upsert_entities_bulk", mock_upsert)

        result = await applier.upsert([entity], UserAgentType.exporter)
        mock_upsert.assert_called_once()
        assert len(result) == 0
        event.entity_topological_sorter.register_entity.assert_called_once_with(entity)


@pytest.mark.asyncio
async def test_using_create_entity_helper(
    mock_ocean: Ocean,
    mock_context: PortOceanContext,
    mock_port_app_config: PortAppConfig,
) -> None:
    applier = HttpEntitiesStateApplier(mock_context)
    entity1 = create_entity("entity1", "service", {"related_to": "entity2"}, False)

    assert entity1.identifier == "entity1"
    assert entity1.blueprint == "service"
    assert entity1.relations == {"related_to": "entity2"}
    assert entity1.properties == {"mock_is_to_fail": False}

    async with event_context(EventType.RESYNC, trigger_type="machine") as event:
        event.port_app_config = mock_port_app_config

        mock_ocean.config.upsert_entities_batch_max_length = 100
        mock_ocean.config.upsert_entities_batch_max_size_in_bytes = 1000

        mock_upsert = AsyncMock(return_value=[(True, entity1)])
        setattr(mock_ocean.port_client, "upsert_entities_bulk", mock_upsert)

        result = await applier.upsert([entity1], UserAgentType.exporter)

        mock_upsert.assert_called_once()
        assert len(result) == 1


@pytest.mark.asyncio
async def test_upsert_groups_entities_by_blueprint(
    mock_ocean: Ocean,
    mock_context: PortOceanContext,
    mock_port_app_config: PortAppConfig,
) -> None:
    """Test that upsert groups entities by blueprint and calls upsert_entities_in_batches separately for each group."""
    applier = HttpEntitiesStateApplier(mock_context)

    # Create entities with different blueprints
    service_entity_1 = Entity(identifier="service_1", blueprint="service")
    service_entity_2 = Entity(identifier="service_2", blueprint="service")
    deployment_entity = Entity(identifier="deployment_1", blueprint="deployment")
    user_entity = Entity(identifier="user_1", blueprint="user")

    entities = [service_entity_1, deployment_entity, service_entity_2, user_entity]

    async with event_context(EventType.RESYNC, trigger_type="machine") as event:
        event.port_app_config = mock_port_app_config

        mock_ocean.config.upsert_entities_batch_max_length = 100
        mock_ocean.config.upsert_entities_batch_max_size_in_bytes = 1000

        # Mock the upsert_entities_in_batches method to track calls
        mock_upsert = AsyncMock()
        mock_upsert.side_effect = [
            [
                (True, service_entity_1),
                (True, service_entity_2),
            ],  # First call for "service" blueprint
            [(True, deployment_entity)],  # Second call for "deployment" blueprint
            [(True, user_entity)],  # Third call for "user" blueprint
        ]
        setattr(mock_ocean.port_client, "upsert_entities_in_batches", mock_upsert)

        result = await applier.upsert(entities, UserAgentType.exporter)

        assert mock_upsert.call_count == 3

        assert len(result) == 4

        calls = mock_upsert.call_args_list

        called_entities_groups = [call[0][0] for call in calls]
        blueprint_counts = {}
        for entities_group in called_entities_groups:
            blueprint = entities_group[0].blueprint
            for entity in entities_group:
                assert entity.blueprint == blueprint
            blueprint_counts[blueprint] = len(entities_group)

        # Verify the expected blueprint counts
        assert blueprint_counts["service"] == 2
        assert blueprint_counts["deployment"] == 1
        assert blueprint_counts["user"] == 1
        assert len(blueprint_counts) == 3
