from typing import Any, Generator, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ReadTimeout

from port_ocean.clients.port.mixins.entities import EntityClientMixin
from port_ocean.core.models import Entity

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
        mock_ocean.config.upsert_entities_batch_max_length = 20
        mock_ocean.config.upsert_entities_batch_max_size_in_bytes = 1024 * 1024  # 1MB
        yield mock_ocean


async def mock_upsert_entities_bulk(
    blueprint: str, entities: list[Entity], *args: Any, **kwargs: Any
) -> list[tuple[bool | None, Entity]]:
    results: list[tuple[bool | None, Entity]] = []
    for entity in entities:
        if entity.identifier == errored_entity_identifier:
            results.append((False, entity))
        else:
            results.append((True, entity))
    return results


async def mock_exception_upsert_entities_bulk(
    blueprint: str, entities: list[Entity], *args: Any, **kwargs: Any
) -> list[tuple[bool | None, Entity]]:
    for entity in entities:
        if entity.identifier == errored_entity_identifier:
            raise ReadTimeout("")
    return [(True, entity) for entity in entities]


@pytest.fixture
async def entity_client(monkeypatch: Any) -> EntityClientMixin:
    entity_client = EntityClientMixin(auth=MagicMock(), client=MagicMock())
    mock = AsyncMock()
    mock.side_effect = mock_upsert_entities_bulk
    monkeypatch.setattr(entity_client, "upsert_entities_bulk", mock)

    return entity_client


def test_calculate_entities_batch_size_empty_list(
    entity_client: EntityClientMixin,
) -> None:
    """Test that empty list returns batch size of 1"""
    assert entity_client.calculate_entities_batch_size([]) == 1


def test_calculate_entities_batch_size_small_entities(
    entity_client: EntityClientMixin,
) -> None:
    """Test that small entities return max batch size"""
    small_entities = [
        Entity(identifier=f"small_{i}", blueprint="test", properties={"small": "value"})
        for i in range(30)
    ]
    # Small entities should allow max batch size
    assert entity_client.calculate_entities_batch_size(small_entities) == 20


def test_calculate_entities_batch_size_large_entities(
    entity_client: EntityClientMixin,
) -> None:
    """Test that large entities reduce batch size"""
    large_entities = [
        Entity(
            identifier=f"large_{i}",
            blueprint="test",
            properties={"large": "x" * (100 * 1024)},  # 100KB per entity
        )
        for i in range(30)
    ]
    # With 1MB limit and 100KB per entity (plus overhead), should get ~9 entities per batch
    batch_size = entity_client.calculate_entities_batch_size(large_entities)
    assert 5 <= batch_size <= 15


def test_calculate_entities_batch_size_mixed_entities(
    entity_client: EntityClientMixin,
) -> None:
    """Test that mixed size entities calculate correct batch size"""
    mixed_entities = [
        Entity(identifier=f"small_{i}", blueprint="test", properties={"small": "value"})
        for i in range(10)
    ] + [
        Entity(
            identifier=f"large_{i}",
            blueprint="test",
            properties={"large": "x" * (50 * 1024)},  # 50KB per entity
        )
        for i in range(10)
    ]
    # With 1MB limit and mixed sizes, should get a reasonable batch size
    batch_size = entity_client.calculate_entities_batch_size(mixed_entities)
    assert 15 <= batch_size <= 20


def test_calculate_entities_batch_size_single_large_entity(
    entity_client: EntityClientMixin,
) -> None:
    """Test that single very large entity returns batch size of 1"""
    large_entity = Entity(
        identifier="huge",
        blueprint="test",
        properties={"huge": "x" * (2 * 1024 * 1024)},  # 2MB entity
    )
    # Even though entity is larger than limit, we return 1 to ensure at least one entity is processed
    assert entity_client.calculate_entities_batch_size([large_entity]) == 1


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
        mock = AsyncMock(side_effect=mock_exception_upsert_entities_bulk)
        monkeypatch.setattr(entity_client, "upsert_entities_bulk", mock)
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
        mock = AsyncMock(side_effect=mock_exception_upsert_entities_bulk)
        monkeypatch.setattr(entity_client, "upsert_entities_bulk", mock)
        with pytest.raises(ReadTimeout):
            await entity_client.upsert_entities_in_batches(
                entities=all_entities, request_options=MagicMock(), should_raise=True
            )


async def test_search_entities_uses_datasource_route_when_query_is_none(
    entity_client: EntityClientMixin,
) -> None:
    """Test that search_entities uses datasource route when query is None"""
    mock_response = MagicMock()
    mock_response.json.return_value = {"entities": []}
    mock_response.is_error = False
    mock_response.status_code = 200
    mock_response.headers = {}
    entity_client.client.post = AsyncMock(return_value=mock_response)  # type: ignore
    entity_client.auth.headers = AsyncMock(  # type: ignore
        return_value={"Authorization": "Bearer test"}
    )

    entity_client.auth.integration_type = "test-integration"
    entity_client.auth.integration_identifier = "test-identifier"
    entity_client.auth.api_url = "https://api.getport.io/v1"

    mock_user_agent_type = MagicMock()
    mock_user_agent_type.value = "sync"

    await entity_client.search_entities(
        user_agent_type=mock_user_agent_type,
        query=None,
    )

    entity_client.client.post.assert_called_once()
    call_args = entity_client.client.post.call_args

    assert (
        call_args[0][0]
        == "https://api.getport.io/v1/blueprints/entities/datasource-entities"
    )

    expected_json = {
        "datasource_prefix": "port-ocean/test-integration/",
        "datasource_suffix": "/test-identifier/sync",
    }
    assert call_args[1]["json"] == expected_json
