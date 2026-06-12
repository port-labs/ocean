from unittest.mock import AsyncMock

import httpx
import pytest
from pytest_httpx import HTTPXMock

from mend.auth.authenticator import MendAuthenticator
from mend.clients.client import MendClient, PAGE_SIZE
from mend.utils import IgnoredError

BASE_URL = "https://api-saas.mend.io"

AUTH_HEADERS = {
    "Authorization": "Bearer test-token",
    "Content-Type": "application/json",
    "agent-name": "pi-port",
    "agent-version": "test-version",
}

REFRESHED_AUTH_HEADERS = {
    "Authorization": "Bearer refreshed-token",
    "Content-Type": "application/json",
    "agent-name": "pi-port",
    "agent-version": "test-version",
}


@pytest.fixture
def mock_authenticator() -> AsyncMock:
    auth = AsyncMock(spec=MendAuthenticator)
    auth.get_auth_headers.return_value = dict(AUTH_HEADERS)
    auth.org_uuid = "test-org-uuid"
    return auth


@pytest.fixture
def client(mock_authenticator: AsyncMock) -> MendClient:
    return MendClient(
        base_url=BASE_URL,
        authenticator=mock_authenticator,
    )


class TestMendClient:
    def test_init(self, client: MendClient) -> None:
        assert client.base_url == BASE_URL
        assert client.org_uuid == "test-org-uuid"

    def test_trailing_slash_stripped(self, mock_authenticator: AsyncMock) -> None:
        c = MendClient(f"{BASE_URL}/", mock_authenticator)
        assert c.base_url == BASE_URL

    def test_page_size_constant(self) -> None:
        assert PAGE_SIZE == 100

    async def test_send_api_request_success(
        self, client: MendClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            url=f"{BASE_URL}/api/v3.0/test",
            json={"response": [{"uuid": "1"}]},
        )

        result = await client.send_api_request("/api/v3.0/test")

        assert result == {"response": [{"uuid": "1"}]}

    async def test_send_api_request_sends_auth_and_agent_headers(
        self, client: MendClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(url=f"{BASE_URL}/api/v3.0/test", json={})

        await client.send_api_request("/api/v3.0/test")

        request = httpx_mock.get_requests()[0]
        assert request.headers["Authorization"] == "Bearer test-token"
        assert request.headers["agent-name"] == "pi-port"
        assert request.headers["agent-version"] == "test-version"

    async def test_send_api_request_401_refreshes_token_and_retries(
        self,
        client: MendClient,
        mock_authenticator: AsyncMock,
        httpx_mock: HTTPXMock,
    ) -> None:
        # First call builds the request headers, second call comes from the
        # retry transport's token refresher after the 401.
        mock_authenticator.get_auth_headers.side_effect = [
            dict(AUTH_HEADERS),
            dict(REFRESHED_AUTH_HEADERS),
        ]
        httpx_mock.add_response(url=f"{BASE_URL}/api/v3.0/test", status_code=401)
        httpx_mock.add_response(
            url=f"{BASE_URL}/api/v3.0/test",
            json={"response": [{"uuid": "1"}]},
        )

        result = await client.send_api_request("/api/v3.0/test")

        assert result == {"response": [{"uuid": "1"}]}
        requests = httpx_mock.get_requests()
        assert len(requests) == 2
        assert requests[0].headers["Authorization"] == "Bearer test-token"
        assert requests[1].headers["Authorization"] == "Bearer refreshed-token"

    async def test_send_api_request_persistent_401_on_post_raises(
        self, client: MendClient, httpx_mock: HTTPXMock
    ) -> None:
        # POST is not a retryable method, so a 401 surfaces immediately
        # instead of going through the token-refresh retry path.
        httpx_mock.add_response(
            method="POST", url=f"{BASE_URL}/api/v3.0/test", status_code=401
        )

        with pytest.raises(httpx.HTTPStatusError):
            await client.send_api_request("/api/v3.0/test", method="POST")

    async def test_send_api_request_403_ignored(
        self, client: MendClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(url=f"{BASE_URL}/api/v3.0/test", status_code=403)

        result = await client.send_api_request("/api/v3.0/test")

        assert result == {}

    async def test_send_api_request_404_ignored(
        self, client: MendClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(url=f"{BASE_URL}/api/v3.0/test", status_code=404)

        result = await client.send_api_request("/api/v3.0/test")

        assert result == {}

    async def test_send_api_request_custom_ignored_error(
        self, client: MendClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(url=f"{BASE_URL}/api/v3.0/test", status_code=410)

        result = await client.send_api_request(
            "/api/v3.0/test",
            ignored_errors=[IgnoredError(status=410, message="Gone")],
        )

        assert result == {}

    async def test_send_api_request_500_raises(
        self, client: MendClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(url=f"{BASE_URL}/api/v3.0/test", status_code=500)

        with pytest.raises(httpx.HTTPStatusError):
            await client.send_api_request("/api/v3.0/test")

    async def test_cursor_paginated_single_page(
        self, client: MendClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            url=f"{BASE_URL}/api/v3.0/test?limit=100",
            json={
                "response": [{"uuid": "1"}, {"uuid": "2"}],
                "additionalData": {"next": None, "cursor": None},
            },
        )

        results = []
        async for batch in client.send_cursor_paginated_request("/api/v3.0/test"):
            results.append(batch)

        assert len(results) == 1
        assert results[0] == [{"uuid": "1"}, {"uuid": "2"}]

    async def test_cursor_paginated_multiple_pages(
        self, client: MendClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            url=f"{BASE_URL}/api/v3.0/test?limit=100",
            json={
                "response": [{"uuid": str(i)} for i in range(100)],
                "additionalData": {"next": True, "cursor": 100},
            },
        )
        httpx_mock.add_response(
            url=f"{BASE_URL}/api/v3.0/test?limit=100&cursor=100",
            json={
                "response": [{"uuid": str(i)} for i in range(100, 140)],
                "additionalData": {"next": None, "cursor": None},
            },
        )

        results = []
        async for batch in client.send_cursor_paginated_request("/api/v3.0/test"):
            results.append(batch)

        assert len(results) == 2
        assert len(results[0]) == 100
        assert len(results[1]) == 40

    async def test_cursor_paginated_empty_response(
        self, client: MendClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            url=f"{BASE_URL}/api/v3.0/test?limit=100",
            json={
                "response": [],
                "additionalData": {"next": None, "cursor": None},
            },
        )

        results = []
        async for batch in client.send_cursor_paginated_request("/api/v3.0/test"):
            results.append(batch)

        assert len(results) == 0

    async def test_cursor_paginated_stops_on_ignored_error(
        self, client: MendClient, httpx_mock: HTTPXMock
    ) -> None:
        # An ignored 404 yields an empty body, which terminates pagination.
        httpx_mock.add_response(
            url=f"{BASE_URL}/api/v3.0/test?limit=100", status_code=404
        )

        results = []
        async for batch in client.send_cursor_paginated_request("/api/v3.0/test"):
            results.append(batch)

        assert results == []

    async def test_cursor_paginated_post_method(
        self, client: MendClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/api/v3.0/test?limit=100",
            json={
                "response": [{"uuid": "1"}],
                "additionalData": {"next": None},
            },
        )

        async for _ in client.send_cursor_paginated_request(
            "/api/v3.0/test", method="POST", json_data={"filter": "value"}
        ):
            pass

        request = httpx_mock.get_requests()[0]
        assert request.method == "POST"
        assert b'"filter"' in request.content
