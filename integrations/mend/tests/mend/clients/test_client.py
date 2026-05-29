from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from mend.auth.authenticator import MendAuthenticator
from mend.clients.client import MendClient, PAGE_SIZE


@pytest.fixture
def mock_authenticator() -> AsyncMock:
    auth = AsyncMock(spec=MendAuthenticator)
    auth.get_auth_headers.return_value = {
        "Authorization": "Bearer test-token",
        "Content-Type": "application/json",
    }
    auth.org_uuid = "test-org-uuid"
    return auth


@pytest.fixture
def client(mock_authenticator: AsyncMock) -> MendClient:
    return MendClient(
        base_url="https://api-saas.mend.io",
        authenticator=mock_authenticator,
    )


class TestMendClient:
    def test_init(self, client: MendClient) -> None:
        assert client.base_url == "https://api-saas.mend.io"
        assert client.org_uuid == "test-org-uuid"

    def test_trailing_slash_stripped(self, mock_authenticator: AsyncMock) -> None:
        c = MendClient("https://api-saas.mend.io/", mock_authenticator)
        assert c.base_url == "https://api-saas.mend.io"

    def test_page_size_constant(self) -> None:
        assert PAGE_SIZE == 100

    @pytest.mark.asyncio
    async def test_send_api_request_success(self, client: MendClient) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": [{"uuid": "1"}]}
        mock_response.raise_for_status.return_value = None

        with patch("mend.clients.client.http_async_client") as mock_http:
            mock_http.request = AsyncMock(return_value=mock_response)
            result = await client.send_api_request("/api/v3.0/test")
            assert result == {"response": [{"uuid": "1"}]}

    @pytest.mark.asyncio
    async def test_send_api_request_401_invalidates_and_retries(
        self, client: MendClient, mock_authenticator: AsyncMock
    ) -> None:
        unauthorized = MagicMock()
        unauthorized.status_code = 401
        unauthorized.text = "Unauthorized"
        unauthorized.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=unauthorized
        )

        ok = MagicMock()
        ok.json.return_value = {"response": [{"uuid": "1"}]}
        ok.raise_for_status.return_value = None

        with patch("mend.clients.client.http_async_client") as mock_http:
            mock_http.request = AsyncMock(side_effect=[unauthorized, ok])
            result = await client.send_api_request("/api/v3.0/test")
            assert result == {"response": [{"uuid": "1"}]}
            mock_authenticator.invalidate_token.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_api_request_persistent_401_raises(
        self, client: MendClient
    ) -> None:
        unauthorized = MagicMock()
        unauthorized.status_code = 401
        unauthorized.text = "Unauthorized"
        unauthorized.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=unauthorized
        )

        with patch("mend.clients.client.http_async_client") as mock_http:
            mock_http.request = AsyncMock(return_value=unauthorized)
            with pytest.raises(httpx.HTTPStatusError):
                await client.send_api_request("/api/v3.0/test")

    @pytest.mark.asyncio
    async def test_send_api_request_403_ignored(self, client: MendClient) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "403", request=MagicMock(), response=mock_response
        )

        with patch("mend.clients.client.http_async_client") as mock_http:
            mock_http.request = AsyncMock(return_value=mock_response)
            result = await client.send_api_request("/api/v3.0/test")
            assert result == {}

    @pytest.mark.asyncio
    async def test_send_api_request_404_ignored(self, client: MendClient) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=mock_response
        )

        with patch("mend.clients.client.http_async_client") as mock_http:
            mock_http.request = AsyncMock(return_value=mock_response)
            result = await client.send_api_request("/api/v3.0/test")
            assert result == {}

    @pytest.mark.asyncio
    async def test_send_api_request_500_raises(self, client: MendClient) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Server Error"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=mock_response
        )

        with patch("mend.clients.client.http_async_client") as mock_http:
            mock_http.request = AsyncMock(return_value=mock_response)
            with pytest.raises(httpx.HTTPStatusError):
                await client.send_api_request("/api/v3.0/test")

    @pytest.mark.asyncio
    async def test_cursor_paginated_single_page(self, client: MendClient) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "response": [{"uuid": "1"}, {"uuid": "2"}],
            "additionalData": {"next": None, "cursor": None},
        }
        mock_response.raise_for_status.return_value = None

        with patch("mend.clients.client.http_async_client") as mock_http:
            mock_http.request = AsyncMock(return_value=mock_response)
            results = []
            async for batch in client.send_cursor_paginated_request("/api/v3.0/test"):
                results.append(batch)

        assert len(results) == 1
        assert results[0] == [{"uuid": "1"}, {"uuid": "2"}]

    @pytest.mark.asyncio
    async def test_cursor_paginated_multiple_pages(self, client: MendClient) -> None:
        mock_response1 = MagicMock()
        mock_response1.json.return_value = {
            "response": [{"uuid": str(i)} for i in range(100)],
            "additionalData": {
                "next": "https://api-saas.mend.io/api?cursor=100",
                "cursor": 100,
            },
        }
        mock_response1.raise_for_status.return_value = None

        mock_response2 = MagicMock()
        mock_response2.json.return_value = {
            "response": [{"uuid": str(i)} for i in range(100, 140)],
            "additionalData": {"next": None, "cursor": None},
        }
        mock_response2.raise_for_status.return_value = None

        with patch("mend.clients.client.http_async_client") as mock_http:
            mock_http.request = AsyncMock(side_effect=[mock_response1, mock_response2])
            results = []
            async for batch in client.send_cursor_paginated_request("/api/v3.0/test"):
                results.append(batch)

        assert len(results) == 2
        assert len(results[0]) == 100
        assert len(results[1]) == 40

    @pytest.mark.asyncio
    async def test_cursor_paginated_empty_response(self, client: MendClient) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "response": [],
            "additionalData": {"next": None, "cursor": None},
        }
        mock_response.raise_for_status.return_value = None

        with patch("mend.clients.client.http_async_client") as mock_http:
            mock_http.request = AsyncMock(return_value=mock_response)
            results = []
            async for batch in client.send_cursor_paginated_request("/api/v3.0/test"):
                results.append(batch)

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_cursor_paginated_passes_cursor_param(
        self, client: MendClient
    ) -> None:
        mock_response1 = MagicMock()
        mock_response1.json.return_value = {
            "response": [{"uuid": "1"}] * 100,
            "additionalData": {"next": "url", "cursor": 100},
        }
        mock_response1.raise_for_status.return_value = None

        mock_response2 = MagicMock()
        mock_response2.json.return_value = {
            "response": [{"uuid": "x"}],
            "additionalData": {"next": None, "cursor": None},
        }
        mock_response2.raise_for_status.return_value = None

        with patch("mend.clients.client.http_async_client") as mock_http:
            mock_http.request = AsyncMock(side_effect=[mock_response1, mock_response2])
            async for _ in client.send_cursor_paginated_request("/api/v3.0/test"):
                pass

        calls = mock_http.request.call_args_list
        assert len(calls) == 2
        first_params = calls[0].kwargs.get("params", {})
        assert "cursor" not in first_params
        second_params = calls[1].kwargs.get("params", {})
        assert second_params.get("cursor") == 100

    @pytest.mark.asyncio
    async def test_cursor_paginated_post_method(self, client: MendClient) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "response": [{"uuid": "1"}],
            "additionalData": {"next": None},
        }
        mock_response.raise_for_status.return_value = None

        with patch("mend.clients.client.http_async_client") as mock_http:
            mock_http.request = AsyncMock(return_value=mock_response)
            async for _ in client.send_cursor_paginated_request(
                "/api/v3.0/test", method="POST", json_data={"filter": "value"}
            ):
                pass

        call_args = mock_http.request.call_args
        assert call_args.kwargs.get("method") == "POST" or call_args.args[0] == "POST"
