from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from plain.client import MAX_PAGE_SIZE, PlainClient
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


def _client(page_size: Any = None) -> PlainClient:
    config: dict[str, Any] = {"api_token": "plainApiKey_test"}
    if page_size is not None:
        config["page_size"] = page_size
    mock_ocean = MagicMock()
    mock_ocean.integration_config = config
    http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(500))
    )
    with patch("plain.client.ocean", mock_ocean):
        return PlainClient(http_client=http_client)


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
    assert seen[0]["first"] == MAX_PAGE_SIZE
    assert seen[0]["after"] is None


async def test_multi_page_follows_end_cursor_in_order() -> None:
    client = _client(page_size="25")
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

    batches = [
        batch
        async for batch in client.paginate_connection(QUERY, OPERATION, {}, "threads")
    ]

    assert batches == [[{"id": "th_1"}]]
    execute.assert_awaited_once()


async def test_page_size_is_capped_at_100() -> None:
    client = _client(page_size=500)
    _, seen = await _pages(
        client,
        [_connection([], has_next_page=False, end_cursor=None)],
    )

    assert seen[0]["first"] == MAX_PAGE_SIZE


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
