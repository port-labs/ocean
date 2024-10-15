from typing import Any
from unittest.mock import MagicMock

import aiohttp
import pytest

from port_ocean.clients.port.mixins.entities import EntityClientMixin
from port_ocean.core.models import Entity

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
        raise aiohttp.ConnectionTimeoutError("")
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
    result_entities = await entity_client.batch_upsert_entities(
        entities=all_entities, request_options=MagicMock(), should_raise=False
    )

    assert result_entities == expected_result_entities


async def test_batch_upsert_entities_read_timeout_should_raise_true(
    entity_client: EntityClientMixin,
) -> None:
    with pytest.raises(aiohttp.ConnectionTimeoutError):
        await entity_client.batch_upsert_entities(
            entities=all_entities, request_options=MagicMock(), should_raise=True
        )
