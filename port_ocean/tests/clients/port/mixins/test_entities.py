from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from port_ocean.clients.port.mixins.entities import EntityClientMixin
from port_ocean.core.models import Entity, EntityRef
from httpx import ReadTimeout


errored_entity_identifier: str = "a"
expected_result_entities = [
    Entity(identifier="b", blueprint="b"),
    Entity(identifier="c", blueprint="c"),
]
entity = Entity(identifier="a", blueprint="a")
all_entities = [
    Entity(identifier=errored_entity_identifier, blueprint="a")
] + expected_result_entities


entity_ref = EntityRef(identifier="a", blueprint="a")
entity_refs = [
    EntityRef(identifier="b", blueprint="b"),
    EntityRef(identifier="c", blueprint="c"),
]


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
    result_entities = await entity_client.batch_upsert_entities(
        entities=all_entities, request_options=MagicMock(), should_raise=False
    )

    assert result_entities == expected_result_entities


async def test_batch_upsert_entities_read_timeout_should_raise_true(
    entity_client: EntityClientMixin,
) -> None:
    with pytest.raises(ReadTimeout):
        await entity_client.batch_upsert_entities(
            entities=all_entities, request_options=MagicMock(), should_raise=True
        )


async def test_delete_entity_ref(
    monkeypatch: Any,
    entity_client: EntityClientMixin,
) -> None:
    # Arrange
    auth = AsyncMock()
    monkeypatch.setattr(entity_client, "auth", auth)
    monkeypatch.setattr(auth, "headers", AsyncMock())
    client = AsyncMock()
    monkeypatch.setattr(entity_client, "client", client)
    monkeypatch.setattr(client, "delete", AsyncMock())

    # Act
    await entity_client.delete_entity(
        entity_ref=entity_ref, request_options=MagicMock(), should_raise=True
    )

    # Assert
    client.delete.assert_called_once()


async def test_delete_entity_ref_with_entity(
    monkeypatch: Any,
    entity_client: EntityClientMixin,
) -> None:
    # Arrange
    auth = AsyncMock()
    monkeypatch.setattr(entity_client, "auth", auth)
    monkeypatch.setattr(auth, "headers", AsyncMock())
    client = AsyncMock()
    monkeypatch.setattr(entity_client, "client", client)
    monkeypatch.setattr(client, "delete", AsyncMock())

    # Act
    await entity_client.delete_entity(
        entity_ref=entity, request_options=MagicMock(), should_raise=True
    )

    # Assert
    client.delete.assert_called_once()


async def test_batch_delete_entities(
    monkeypatch: Any,
    entity_client: EntityClientMixin,
) -> None:
    # Arrange
    auth = AsyncMock()
    monkeypatch.setattr(entity_client, "auth", auth)
    monkeypatch.setattr(auth, "headers", AsyncMock())
    client = AsyncMock()
    monkeypatch.setattr(entity_client, "client", client)
    monkeypatch.setattr(client, "delete", AsyncMock())

    # Act
    await entity_client.batch_delete_entities(
        entities_refs=entity_refs, request_options=MagicMock(), should_raise=True
    )

    # Assert
    assert client.delete.call_count == 2


async def test_search_entities_refs(
    monkeypatch: Any,
    entity_client: EntityClientMixin,
) -> None:
    # Arrange
    auth = AsyncMock()
    monkeypatch.setattr(entity_client, "auth", auth)
    monkeypatch.setattr(auth, "headers", AsyncMock())
    client = AsyncMock()
    mock_entities_response = {
        "entities": [
            {"identifier": "b", "blueprint": "b"},
            {"identifier": "c", "blueprint": "c"},
        ]
    }
    response = AsyncMock()
    response.json = MagicMock()
    response.json.return_value = mock_entities_response
    monkeypatch.setattr(entity_client, "client", client)
    client.post.return_value = response

    # Act
    actual_results = await entity_client.search_entities_refs(
        user_agent_type=MagicMock(), query={}
    )

    # Assert
    client.post.assert_called_once()
    assert actual_results == entity_refs


async def test_search_entities(
    monkeypatch: Any,
    entity_client: EntityClientMixin,
) -> None:
    # Arrange
    auth = AsyncMock()
    monkeypatch.setattr(entity_client, "auth", auth)
    monkeypatch.setattr(auth, "headers", AsyncMock())
    client = AsyncMock()
    mock_entities_response = {
        "entities": [
            {"identifier": "b", "blueprint": "b"},
            {"identifier": "c", "blueprint": "c"},
        ]
    }
    response = AsyncMock()
    response.json = MagicMock()
    response.json.return_value = mock_entities_response
    monkeypatch.setattr(entity_client, "client", client)
    client.post.return_value = response

    # Act
    actual_results = await entity_client.search_entities(
        user_agent_type=MagicMock(), query={}
    )

    # Assert
    client.post.assert_called_once()
    assert actual_results == expected_result_entities


async def test_search_batch_entities_refs(
    monkeypatch: Any,
    entity_client: EntityClientMixin,
) -> None:
    # Arrange
    auth = AsyncMock()
    monkeypatch.setattr(entity_client, "auth", auth)
    monkeypatch.setattr(auth, "headers", AsyncMock())
    monkeypatch.setattr(entity_client, "search_entities", AsyncMock())
    monkeypatch.setattr(entity_client, "_generate_search_query", MagicMock())

    # Act
    await entity_client.search_batch_entities_refs(
        user_agent_type=MagicMock(), entities_to_search=[]
    )

    # Assert
    entity_client.search_entities.assert_called_once()


async def test_search_batch_entities(
    monkeypatch: Any,
    entity_client: EntityClientMixin,
) -> None:
    # Arrange
    auth = AsyncMock()
    monkeypatch.setattr(entity_client, "auth", auth)
    monkeypatch.setattr(auth, "headers", AsyncMock())
    monkeypatch.setattr(entity_client, "search_entities", AsyncMock())
    monkeypatch.setattr(entity_client, "_generate_search_query", MagicMock())

    # Act
    await entity_client.search_batch_entities(
        user_agent_type=MagicMock(), entities_to_search=[]
    )

    # Assert
    entity_client.search_entities.assert_called_once()
