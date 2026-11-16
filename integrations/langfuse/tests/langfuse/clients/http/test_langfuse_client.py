from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from langfuse.clients.http.langfuse_client import LangfuseClient


@pytest.mark.asyncio
class TestLangfuseClient:
    def _client(self) -> LangfuseClient:
        return LangfuseClient(
            host="https://cloud.langfuse.com",
            public_key="pk",
            secret_key="sk",
        )

    async def test_send_api_request_success(self) -> None:
        client = self._client()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.content = b'{"data":[]}'
        mock_response.json.return_value = {"data": []}

        with patch(
            "port_ocean.helpers.async_client.OceanAsyncClient.request",
            AsyncMock(return_value=mock_response),
        ):
            result = await client.send_api_request("projects")
            assert result == {"data": []}

    async def test_send_api_request_404_returns_empty(self) -> None:
        client = self._client()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.text = "missing"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=mock_response
        )

        with patch(
            "port_ocean.helpers.async_client.OceanAsyncClient.request",
            AsyncMock(return_value=mock_response),
        ):
            assert await client.send_api_request("v2/prompts/missing") == {}

    async def test_send_paginated_request_stops_at_total_pages(self) -> None:
        client = self._client()
        pages = [
            {
                "data": [{"name": "a"}],
                "meta": {"page": 1, "limit": 100, "totalItems": 2, "totalPages": 2},
            },
            {
                "data": [{"name": "b"}],
                "meta": {"page": 2, "limit": 100, "totalItems": 2, "totalPages": 2},
            },
        ]
        client.send_api_request = AsyncMock(side_effect=pages)  # type: ignore[method-assign]

        batches = [batch async for batch in client.send_paginated_request("v2/prompts")]
        assert batches == [[{"name": "a"}], [{"name": "b"}]]
        assert client.send_api_request.await_count == 2
