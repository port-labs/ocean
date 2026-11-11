from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from confluence.clients.client import ConfluenceClient
from confluence.helpers.exceptions import (
    ConfluenceAuthenticationError,
    MissingConfluencePermissionError,
)


def _client() -> ConfluenceClient:
    return ConfluenceClient(
        site_url="https://example.atlassian.net",
        email="docs@example.com",
        api_token="test-token",
    )


def _response(status_code: int, payload: object, url: str) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=payload,
        request=httpx.Request("GET", url),
    )


@pytest.mark.asyncio
class TestConfluenceClient:
    async def test_send_api_request_success(self) -> None:
        client = _client()
        url = "https://example.atlassian.net/wiki/api/v2/spaces/123"
        client.http_client = MagicMock()
        client.http_client.request = AsyncMock(
            return_value=_response(200, {"id": "123", "key": "DOCS"}, url)
        )

        result = await client.send_api_request("spaces/123")

        assert result == {"id": "123", "key": "DOCS"}
        request_kwargs = client.http_client.request.await_args.kwargs
        assert request_kwargs["url"] == url
        assert request_kwargs["headers"]["Authorization"].startswith("Basic ")

    async def test_send_api_request_404_returns_empty_object(self) -> None:
        client = _client()
        client.http_client = MagicMock()
        client.http_client.request = AsyncMock(
            return_value=_response(
                404,
                {"message": "Not found"},
                "https://example.atlassian.net/wiki/api/v2/pages/1",
            )
        )

        assert await client.send_api_request("pages/1", missing_ok=True) == {}

    async def test_send_api_request_404_raises_for_lists(self) -> None:
        client = _client()
        client.http_client = MagicMock()
        client.http_client.request = AsyncMock(
            return_value=_response(
                404,
                {"message": "Not found"},
                "https://example.atlassian.net/wiki/api/v2/pages",
            )
        )

        with pytest.raises(httpx.HTTPStatusError):
            await client.send_api_request("pages")

    async def test_send_api_request_401_raises(self) -> None:
        client = _client()
        client.http_client = MagicMock()
        client.http_client.request = AsyncMock(
            return_value=_response(
                401,
                {"message": "Client must be authenticated"},
                "https://example.atlassian.net/wiki/api/v2/spaces",
            )
        )

        with pytest.raises(ConfluenceAuthenticationError, match="API token"):
            await client.send_api_request("spaces")

    async def test_send_api_request_403_names_required_access(self) -> None:
        client = _client()
        client.http_client = MagicMock()
        client.http_client.request = AsyncMock(
            return_value=_response(
                403,
                {
                    "errors": [
                        {"status": 403, "title": "Forbidden", "detail": "Not permitted"}
                    ]
                },
                "https://example.atlassian.net/wiki/api/v2/pages",
            )
        )

        with pytest.raises(MissingConfluencePermissionError, match="view Confluence"):
            await client.send_api_request("pages")

    async def test_send_api_request_500_raises(self) -> None:
        client = _client()
        client.http_client = MagicMock()
        client.http_client.request = AsyncMock(
            return_value=_response(
                500,
                {"message": "unavailable"},
                "https://example.atlassian.net/wiki/api/v2/spaces",
            )
        )

        with pytest.raises(httpx.HTTPStatusError):
            await client.send_api_request("spaces")

    async def test_absolute_path_uses_the_site_url(self) -> None:
        client = _client()
        url = "https://example.atlassian.net/wiki/rest/api/search/user"
        client.http_client = MagicMock()
        client.http_client.request = AsyncMock(
            return_value=_response(200, {"results": []}, url)
        )

        await client.send_api_request(
            "/wiki/rest/api/search/user", params={"cql": "type=user"}
        )

        assert client.http_client.request.await_args.kwargs["url"] == url

    async def test_send_paginated_request_follows_next_link(self) -> None:
        client = _client()
        pages = [
            {
                "results": [{"id": "1"}],
                "_links": {"next": "/wiki/api/v2/spaces?limit=100&cursor=abc"},
            },
            {"results": [{"id": "2"}], "_links": {}},
        ]
        client.send_api_request = AsyncMock(side_effect=pages)  # type: ignore[method-assign]

        batches = [
            batch
            async for batch in client.send_paginated_request(
                "spaces", params={"status": "current"}
            )
        ]

        assert batches == [[{"id": "1"}], [{"id": "2"}]]
        first_call = client.send_api_request.await_args_list[0]
        second_call = client.send_api_request.await_args_list[1]
        assert first_call.args == ("spaces",)
        assert first_call.kwargs["params"]["limit"] == 100
        assert first_call.kwargs["params"]["status"] == "current"
        assert second_call.args == ("/wiki/api/v2/spaces?limit=100&cursor=abc",)
        assert second_call.kwargs["params"] is None

    async def test_send_paginated_request_stops_when_next_link_repeats(self) -> None:
        client = _client()
        repeated = "/wiki/api/v2/spaces?cursor=abc"
        client.send_api_request = AsyncMock(  # type: ignore[method-assign]
            return_value={"results": [{"id": "1"}], "_links": {"next": repeated}}
        )

        batches = [batch async for batch in client.send_paginated_request("spaces")]

        assert batches == [[{"id": "1"}], [{"id": "1"}]]
        assert client.send_api_request.await_count == 2
