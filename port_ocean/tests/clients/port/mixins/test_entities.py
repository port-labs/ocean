from typing import Any, List, Generator
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from port_ocean.clients.port.mixins.entities import EntityClientMixin
from port_ocean.core.models import Entity
from httpx import ReadTimeout

# Mock the ocean context at module level
pytestmark = pytest.mark.usefixtures("mock_ocean")


errored_entity_identifier: str = "a"
expected_result_entities: List[Entity] = [
    Entity(identifier="b", blueprint="b"),
    Entity(identifier="c", blueprint="c"),
]
expected_result_entities_with_exception: List[Entity] = []
all_entities: List[Entity] = [
    Entity(identifier=errored_entity_identifier, blueprint="a")
] + expected_result_entities


@pytest.fixture(autouse=True)
def mock_ocean() -> Generator[MagicMock, None, None]:
    with patch("port_ocean.clients.port.mixins.entities.ocean") as mock_ocean:
        mock_ocean.config.upsert_entities_batch_size = 20
        yield mock_ocean


async def mock_upsert_entities_batch(
    entities: list[Entity], *args: Any, **kwargs: Any
) -> list[tuple[bool | None, Entity]]:
    results: list[tuple[bool | None, Entity]] = []
    for entity in entities:
        if entity.identifier == errored_entity_identifier:
            results.append((False, entity))
        else:
            results.append((True, entity))
    return results


async def mock_exception_upsert_entities_batch(
    entities: list[Entity], *args: Any, **kwargs: Any
) -> list[tuple[bool | None, Entity]]:
    for entity in entities:
        if entity.identifier == errored_entity_identifier:
            raise ReadTimeout("")
    return [(True, entity) for entity in entities]


@pytest.fixture
async def entity_client(monkeypatch: Any) -> EntityClientMixin:
    entity_client = EntityClientMixin(auth=MagicMock(), client=MagicMock())
    mock = AsyncMock()
    mock.side_effect = mock_upsert_entities_batch
    monkeypatch.setattr(entity_client, "upsert_entities_batch", mock)

    return entity_client


async def test_batch_upsert_entities_read_timeout_should_raise_false(
    entity_client: EntityClientMixin,
) -> None:
    with patch("port_ocean.context.event.event", MagicMock()):
        result_entities = await entity_client.upsert_entities_in_batches(
            entities=all_entities, request_options=MagicMock(), should_raise=False
        )
        # Only get entities that were successfully upserted (status is True)
        entities_only = [entity for status, entity in result_entities if status is True]

        assert entities_only == expected_result_entities


async def test_batch_upsert_entities_read_timeout_should_raise_false_with_exception(
    entity_client: EntityClientMixin,
    monkeypatch: Any,
) -> None:
    with patch("port_ocean.context.event.event", MagicMock()):
        # Override the mock for this test to use the exception-throwing version
        mock = AsyncMock(side_effect=mock_exception_upsert_entities_batch)
        monkeypatch.setattr(entity_client, "upsert_entities_batch", mock)
        result_entities = await entity_client.upsert_entities_in_batches(
            entities=all_entities, request_options=MagicMock(), should_raise=False
        )
        # Only get entities that were successfully upserted (status is True)
        entities_only = [entity for status, entity in result_entities if status is True]

        assert entities_only == expected_result_entities_with_exception


async def test_batch_upsert_entities_read_timeout_should_raise_true(
    entity_client: EntityClientMixin,
    monkeypatch: Any,
) -> None:
    with patch("port_ocean.context.event.event", MagicMock()):
        # Override the mock for this test to use the exception-throwing version
        mock = AsyncMock(side_effect=mock_exception_upsert_entities_batch)
        monkeypatch.setattr(entity_client, "upsert_entities_batch", mock)
        with pytest.raises(ReadTimeout):
            await entity_client.upsert_entities_in_batches(
                entities=all_entities, request_options=MagicMock(), should_raise=True
            )
