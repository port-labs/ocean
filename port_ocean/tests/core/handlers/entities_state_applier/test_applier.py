from unittest.mock import Mock, patch
import pytest
from port_ocean.core.handlers.entities_state_applier.port.applier import (
    HttpEntitiesStateApplier,
)
from port_ocean.core.models import Entity
from port_ocean.core.ocean_types import EntityDiff
from port_ocean.clients.port.types import UserAgentType


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
async def test_delete_diff_below_threshold() -> None:
    applier = HttpEntitiesStateApplier(Mock())
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
async def test_delete_diff_above_default_threshold() -> None:
    applier = HttpEntitiesStateApplier(Mock())
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
async def test_delete_diff_custom_threshold_above_threshold_not_deleted() -> None:
    applier = HttpEntitiesStateApplier(Mock())
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
