from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from port_ocean.context.resource import resource_context
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from pydantic.v1 import ValidationError

from integration import ThreadResourceConfig
from plain.client import PlainClient
from plain.exceptions import PlainGraphQLError

QUERY = "query ListThreads { threads { edges { node { id } } } }"
OPERATION = "ListThreads"


def _connection(
    nodes: list[dict[str, str]],
    *,
    has_next_page: bool,
    end_cursor: str | None,
) -> dict[str, Any]:
    return {
        "threads": {
            "edges": [{"cursor": node["id"], "node": node} for node in nodes],
            "pageInfo": {"hasNextPage": has_next_page, "endCursor": end_cursor},
        }
    }


def _client() -> PlainClient:
    config: dict[str, Any] = {
        "api_token": "plainApiKey_test",
        "api_url": "https://core-api.uk.plain.com/graphql/v1",
    }
    mock_ocean = MagicMock()
    mock_ocean.integration_config = config
    mock_ocean.config.integration.identifier = "plain"
    http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(500))
    )
    with patch("plain.client.ocean", mock_ocean):
        return PlainClient(http_client=http_client)


def _resource(page_size: int = 100) -> ResourceConfig:
    config = ThreadResourceConfig.parse_obj(
        {
            "kind": "thread",
            "selector": {
                "query": "true",
                "pageSize": page_size,
            },
            "port": {
                "entity": {
                    "mappings": {
                        "identifier": ".id",
                        "blueprint": '"plainThread"',
                    }
                }
            },
        }
    )
    return config


async def _pages(
    client: PlainClient,
    responses: list[dict[str, Any]],
    variables: dict[str, Any] | None = None,
) -> tuple[list[list[dict[str, Any]]], list[dict[str, Any]]]:
    seen: list[dict[str, Any]] = []

    async def execute(
        query: str,
        page_variables: dict[str, Any] | None = None,
        operation_name: str | None = None,
    ) -> dict[str, Any]:
        assert query == QUERY
        assert operation_name == OPERATION
        assert page_variables is not None
        seen.append(page_variables)
        return responses[len(seen) - 1]

    client.execute = execute  # type: ignore[assignment]
    batches = [
        batch
        async for batch in client.paginate_connection(
            QUERY, OPERATION, variables, "data.threads"
        )
    ]
    return batches, seen


async def test_single_page_yields_one_batch_and_stops() -> None:
    client = _client()
    async with resource_context(_resource()):
        batches, seen = await _pages(
            client,
            [
                _connection(
                    [{"id": "th_1"}],
                    has_next_page=False,
                    end_cursor="cursor-1",
                )
            ],
        )

    assert batches == [[{"id": "th_1"}]]
    assert len(seen) == 1
    assert seen[0]["first"] == 100
    assert seen[0]["after"] is None


async def test_multi_page_follows_end_cursor_in_order() -> None:
    client = _client()
    async with resource_context(_resource(page_size=25)):
        batches, seen = await _pages(
            client,
            [
                _connection(
                    [{"id": "th_1"}],
                    has_next_page=True,
                    end_cursor="cursor-1",
                ),
                _connection(
                    [{"id": "th_2"}],
                    has_next_page=True,
                    end_cursor="cursor-2",
                ),
                _connection(
                    [{"id": "th_3"}],
                    has_next_page=False,
                    end_cursor=None,
                ),
            ],
            variables={"filters": {"statuses": ["TODO"]}},
        )

    assert batches == [[{"id": "th_1"}], [{"id": "th_2"}], [{"id": "th_3"}]]
    assert [page["after"] for page in seen] == [None, "cursor-1", "cursor-2"]
    assert [page["first"] for page in seen] == [25, 25, 25]
    assert all(page["filters"] == {"statuses": ["TODO"]} for page in seen)


async def test_empty_connection_yields_one_empty_batch() -> None:
    client = _client()
    async with resource_context(_resource()):
        batches, seen = await _pages(
            client,
            [_connection([], has_next_page=False, end_cursor=None)],
        )

    assert batches == [[]]
    assert len(seen) == 1


async def test_does_not_request_another_page_when_has_next_page_is_false() -> None:
    client = _client()
    execute = AsyncMock(
        return_value=_connection(
            [{"id": "th_1"}],
            has_next_page=False,
            end_cursor="cursor-1",
        )
    )
    client.execute = execute  # type: ignore[method-assign]

    async with resource_context(_resource()):
        batches = [
            batch
            async for batch in client.paginate_connection(
                QUERY, OPERATION, {}, "threads"
            )
        ]

    assert batches == [[{"id": "th_1"}]]
    execute.assert_awaited_once()


async def test_page_size_comes_from_selector() -> None:
    client = _client()
    async with resource_context(_resource(page_size=50)):
        _, seen = await _pages(
            client,
            [_connection([], has_next_page=False, end_cursor=None)],
        )

    assert seen[0]["first"] == 50


def test_page_size_selector_rejects_values_above_100() -> None:
    with pytest.raises(ValidationError):
        ThreadResourceConfig.parse_obj(
            {
                "kind": "thread",
                "selector": {"query": "true", "pageSize": 500},
                "port": {
                    "entity": {
                        "mappings": {
                            "identifier": ".id",
                            "blueprint": '"plainThread"',
                        }
                    }
                },
            }
        )


async def test_page_size_defaults_to_100_outside_resource_context() -> None:
    client = _client()
    _, seen = await _pages(
        client,
        [_connection([], has_next_page=False, end_cursor=None)],
    )

    assert seen[0]["first"] == 100


async def test_page_size_reads_selector_without_local_config_class() -> None:
    client = _client()
    config = ResourceConfig.parse_obj(
        {
            "kind": "thread",
            "selector": {"query": "true"},
            "port": {
                "entity": {
                    "mappings": {
                        "identifier": ".id",
                        "blueprint": '"plainThread"',
                    }
                }
            },
        }
    )
    # Simulate Ocean loading a second copy of the selector model.
    config.selector = SimpleNamespace(page_size=40)  # type: ignore[assignment]

    async with resource_context(config):
        _, seen = await _pages(
            client,
            [_connection([], has_next_page=False, end_cursor=None)],
        )

    assert seen[0]["first"] == 40


async def test_graphql_error_is_not_treated_as_an_empty_page() -> None:
    client = _client()
    client.execute = AsyncMock(  # type: ignore[method-assign]
        side_effect=PlainGraphQLError([{"message": "Missing permission thread:read"}])
    )

    with pytest.raises(PlainGraphQLError, match="Missing permission thread:read"):
        async for _batch in client.paginate_connection(
            QUERY, OPERATION, {}, "data.threads"
        ):
            pass
