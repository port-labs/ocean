from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from port_ocean.clients.port.mixins.entities import EntityClientMixin
from port_ocean.core.models import Entity
from httpx import ReadTimeout


errored_entity_identifier: str = "a"
expected_result_entities = [
    Entity(identifier="b", blueprint="b"),
    Entity(identifier="c", blueprint="c"),
]
all_entities = [
    Entity(identifier=errored_entity_identifier, blueprint="a")
] + expected_result_entities


async def mock_upsert_entity(entity: Entity, *args: Any, **kwargs: Any) -> Entity:
    if entity.identifier == errored_entity_identifier:
        raise ReadTimeout("")
    else:
        return entity


@pytest.fixture
async def entity_client(monkeypatch: Any) -> EntityClientMixin:
    # Arrange
    entity_client = EntityClientMixin(auth=MagicMock(), client=MagicMock())
    monkeypatch.setattr(entity_client, "upsert_entity", mock_upsert_entity)

    return entity_client


async def test_batch_upsert_entities_read_timeout_should_raise_false(
    entity_client: EntityClientMixin,
) -> None:
    with patch("port_ocean.context.event.event", MagicMock()):
        result_entities = await entity_client.batch_upsert_entities(
            entities=all_entities, request_options=MagicMock(), should_raise=False
        )
        entities_only = [entity for _, entity in result_entities]

        assert entities_only == expected_result_entities


async def test_batch_upsert_entities_read_timeout_should_raise_true(
    entity_client: EntityClientMixin,
) -> None:
    with patch("port_ocean.context.event.event", MagicMock()):
        with pytest.raises(ReadTimeout):
            await entity_client.batch_upsert_entities(
                entities=all_entities, request_options=MagicMock(), should_raise=True
            )
