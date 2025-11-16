"""Tests for HTTP Server client"""

from typing import Any
import pytest
from unittest.mock import AsyncMock, patch
from http_server.client import HttpServerClient


class TestHttpServerClient:
    """Test cases for HttpServerClient"""

    def test_client_initialization_no_auth(self) -> None:
        """Test client can be initialized with no authentication"""
        client = HttpServerClient(
            base_url="http://localhost:8080",
            auth_type="none",
            auth_config={},
            pagination_config={},
        )
        assert client.base_url == "http://localhost:8080"
        assert client.auth_type == "none"

    def test_client_with_bearer_auth(self) -> None:
        """Test client initialization with bearer token auth"""
        client = HttpServerClient(
            base_url="http://localhost:8080",
            auth_type="bearer_token",
            auth_config={"api_token": "test-token"},
            pagination_config={},
        )
        assert client.auth_type == "bearer_token"

    def test_client_with_basic_auth(self) -> None:
        """Test client initialization with basic auth"""
        client = HttpServerClient(
            base_url="http://localhost:8080",
            auth_type="basic",
            auth_config={"username": "user", "password": "pass"},
            pagination_config={},
        )
        assert client.auth_type == "basic"

    def test_client_with_api_key_auth(self) -> None:
        """Test client initialization with API key auth"""
        client = HttpServerClient(
            base_url="http://localhost:8080",
            auth_type="api_key",
            auth_config={"api_key": "test-key"},
            pagination_config={},
        )
        assert client.auth_type == "api_key"

    async def test_url_construction_base_with_trailing_slash(self) -> None:
        """Test URL construction when base_url has trailing slash"""
        client = HttpServerClient(
            base_url="https://api.example.com/",
            auth_type="none",
            auth_config={},
            pagination_config={"pagination_type": "none"},
        )

        captured_url: str | None = None

        async def mock_make_request(
            url: str, method: str, params: dict[str, Any], headers: dict[str, str]
        ) -> AsyncMock:
            nonlocal captured_url
            captured_url = url
            response = AsyncMock()
            response.json = AsyncMock(return_value={"data": []})
            response.raise_for_status = lambda: None
            return response

        with patch.object(client, "_make_request", mock_make_request):
            async for _ in client.fetch_paginated_data(endpoint="/v1/users"):
                break

        assert captured_url == "https://api.example.com/v1/users"

    async def test_url_construction_base_with_path_component(self) -> None:
        """Test URL construction preserves base URL path components"""
        client = HttpServerClient(
            base_url="https://rackview-api.dc.adform.zone/api",
            auth_type="none",
            auth_config={},
            pagination_config={"pagination_type": "none"},
        )

        captured_url: str | None = None

        async def mock_make_request(
            url: str, method: str, params: dict[str, Any], headers: dict[str, str]
        ) -> AsyncMock:
            nonlocal captured_url
            captured_url = url
            response = AsyncMock()
            response.json = AsyncMock(return_value={"data": []})
            response.raise_for_status = lambda: None
            return response

        with patch.object(client, "_make_request", mock_make_request):
            async for _ in client.fetch_paginated_data(endpoint="/v2/sit/export"):
                break

        assert captured_url == "https://rackview-api.dc.adform.zone/api/v2/sit/export"

    async def test_url_construction_base_with_path_and_trailing_slash(self) -> None:
        """Test URL construction with base URL path and trailing slash"""
        client = HttpServerClient(
            base_url="https://slack.com/api/",
            auth_type="none",
            auth_config={},
            pagination_config={"pagination_type": "none"},
        )

        captured_url: str | None = None

        async def mock_make_request(
            url: str, method: str, params: dict[str, Any], headers: dict[str, str]
        ) -> AsyncMock:
            nonlocal captured_url
            captured_url = url
            response = AsyncMock()
            response.json = AsyncMock(return_value={"data": []})
            response.raise_for_status = lambda: None
            return response

        with patch.object(client, "_make_request", mock_make_request):
            async for _ in client.fetch_paginated_data(endpoint="/users.list"):
                break

        assert captured_url == "https://slack.com/api/users.list"

    async def test_url_construction_endpoint_without_leading_slash(self) -> None:
        """Test URL construction when endpoint doesn't have leading slash"""
        client = HttpServerClient(
            base_url="https://api.example.com",
            auth_type="none",
            auth_config={},
            pagination_config={"pagination_type": "none"},
        )

        captured_url: str | None = None

        async def mock_make_request(
            url: str, method: str, params: dict[str, Any], headers: dict[str, str]
        ) -> AsyncMock:
            nonlocal captured_url
            captured_url = url
            response = AsyncMock()
            response.json = AsyncMock(return_value={"data": []})
            response.raise_for_status = lambda: None
            return response

        with patch.object(client, "_make_request", mock_make_request):
            async for _ in client.fetch_paginated_data(endpoint="v1/users"):
                break

        assert captured_url == "https://api.example.com/v1/users"

    async def test_url_construction_multiple_trailing_slashes(self) -> None:
        """Test URL construction handles multiple trailing slashes in base_url"""
        client = HttpServerClient(
            base_url="https://api.example.com///",
            auth_type="none",
            auth_config={},
            pagination_config={"pagination_type": "none"},
        )

        captured_url: str | None = None

        async def mock_make_request(
            url: str, method: str, params: dict[str, Any], headers: dict[str, str]
        ) -> AsyncMock:
            nonlocal captured_url
            captured_url = url
            response = AsyncMock()
            response.json = AsyncMock(return_value={"data": []})
            response.raise_for_status = lambda: None
            return response

        with patch.object(client, "_make_request", mock_make_request):
            async for _ in client.fetch_paginated_data(endpoint="/v1/users"):
                break

        assert captured_url == "https://api.example.com/v1/users"

    async def test_url_construction_multiple_leading_slashes(self) -> None:
        """Test URL construction handles multiple leading slashes in endpoint"""
        client = HttpServerClient(
            base_url="https://api.example.com",
            auth_type="none",
            auth_config={},
            pagination_config={"pagination_type": "none"},
        )

        captured_url: str | None = None

        async def mock_make_request(
            url: str, method: str, params: dict[str, Any], headers: dict[str, str]
        ) -> AsyncMock:
            nonlocal captured_url
            captured_url = url
            response = AsyncMock()
            response.json = AsyncMock(return_value={"data": []})
            response.raise_for_status = lambda: None
            return response

        with patch.object(client, "_make_request", mock_make_request):
            async for _ in client.fetch_paginated_data(endpoint="///v1/users"):
                break

        assert captured_url == "https://api.example.com/v1/users"

    async def test_url_construction_with_port_number(self) -> None:
        """Test URL construction with port number in base_url"""
        client = HttpServerClient(
            base_url="http://localhost:8080",
            auth_type="none",
            auth_config={},
            pagination_config={"pagination_type": "none"},
        )

        captured_url: str | None = None

        async def mock_make_request(
            url: str, method: str, params: dict[str, Any], headers: dict[str, str]
        ) -> AsyncMock:
            nonlocal captured_url
            captured_url = url
            response = AsyncMock()
            response.json = AsyncMock(return_value={"data": []})
            response.raise_for_status = lambda: None
            return response

        with patch.object(client, "_make_request", mock_make_request):
            async for _ in client.fetch_paginated_data(endpoint="/api/v1/users"):
                break

        assert captured_url == "http://localhost:8080/api/v1/users"

    async def test_url_construction_deep_path(self) -> None:
        """Test URL construction with deep nested paths"""
        client = HttpServerClient(
            base_url="https://api.example.com/v1/tenant/12345",
            auth_type="none",
            auth_config={},
            pagination_config={"pagination_type": "none"},
        )

        captured_url: str | None = None

        async def mock_make_request(
            url: str, method: str, params: dict[str, Any], headers: dict[str, str]
        ) -> AsyncMock:
            nonlocal captured_url
            captured_url = url
            response = AsyncMock()
            response.json = AsyncMock(return_value={"data": []})
            response.raise_for_status = lambda: None
            return response

        with patch.object(client, "_make_request", mock_make_request):
            async for _ in client.fetch_paginated_data(endpoint="/resources/users"):
                break

        assert captured_url == "https://api.example.com/v1/tenant/12345/resources/users"

    async def test_url_construction_empty_base_url_raises_error(self) -> None:
        """Test that empty base_url raises ValueError"""
        client = HttpServerClient(
            base_url="",
            auth_type="none",
            auth_config={},
            pagination_config={"pagination_type": "none"},
        )

        with pytest.raises(ValueError, match="base_url cannot be empty"):
            await client.fetch_paginated_data(endpoint="/users").__anext__()

    async def test_url_construction_empty_endpoint_raises_error(self) -> None:
        """Test that empty endpoint raises ValueError"""
        client = HttpServerClient(
            base_url="https://api.example.com",
            auth_type="none",
            auth_config={},
            pagination_config={"pagination_type": "none"},
        )

        with pytest.raises(ValueError, match="endpoint cannot be empty"):
            await client.fetch_paginated_data(endpoint="").__anext__()

    async def test_url_construction_endpoint_only_slash_raises_error(self) -> None:
        """Test that endpoint with only slash raises ValueError"""
        client = HttpServerClient(
            base_url="https://api.example.com",
            auth_type="none",
            auth_config={},
            pagination_config={"pagination_type": "none"},
        )

        with pytest.raises(ValueError, match="endpoint cannot be empty"):
            await client.fetch_paginated_data(endpoint="/").__anext__()

    async def test_custom_headers_merged_with_endpoint_headers(self) -> None:
        """Test that global custom headers are merged with per-endpoint headers"""
        client = HttpServerClient(
            base_url="https://api.example.com",
            auth_type="none",
            auth_config={},
            pagination_config={"pagination_type": "none"},
            custom_headers={"X-Version": "v2", "Accept": "application/json"},
        )

        captured_headers: dict[str, str] | None = None

        async def mock_make_request(
            url: str, method: str, params: dict[str, Any], headers: dict[str, str]
        ) -> AsyncMock:
            nonlocal captured_headers
            captured_headers = headers
            response = AsyncMock()
            response.json = AsyncMock(return_value={"data": []})
            response.raise_for_status = lambda: None
            return response

        # Patch the method on the instance before calling fetch_paginated_data
        with patch.object(client, "_make_request", mock_make_request):
            # Call with per-endpoint headers
            async for _ in client.fetch_paginated_data(
                endpoint="/api/v1/users",
                headers={"Accept": "application/vnd.api+json", "X-Custom": "endpoint"},
            ):
                break

        # Verify merged headers: global + endpoint (endpoint overrides global)
        assert captured_headers is not None
        assert captured_headers["X-Version"] == "v2"  # From global
        assert (
            captured_headers["Accept"] == "application/vnd.api+json"
        )  # Overridden by endpoint
        assert captured_headers["X-Custom"] == "endpoint"  # From endpoint

    async def test_custom_headers_only_global(self) -> None:
        """Test that global custom headers are applied when no endpoint headers"""
        client = HttpServerClient(
            base_url="https://api.example.com",
            auth_type="none",
            auth_config={},
            pagination_config={"pagination_type": "none"},
            custom_headers={"X-Version": "v2", "Accept": "application/json"},
        )

        captured_headers: dict[str, str] | None = None

        async def mock_make_request(
            url: str, method: str, params: dict[str, Any], headers: dict[str, str]
        ) -> AsyncMock:
            nonlocal captured_headers
            captured_headers = headers
            response = AsyncMock()
            response.json = AsyncMock(return_value={"data": []})
            response.raise_for_status = lambda: None
            return response

        # Patch the method on the instance before calling fetch_paginated_data
        with patch.object(client, "_make_request", mock_make_request):
            # Call without per-endpoint headers
            async for _ in client.fetch_paginated_data(endpoint="/api/v1/users"):
                break

        # Verify global headers are applied
        assert captured_headers is not None
        assert captured_headers["X-Version"] == "v2"
        assert captured_headers["Accept"] == "application/json"

    async def test_custom_headers_empty_when_not_provided(self) -> None:
        """Test that custom_headers defaults to empty dict when not provided"""
        client = HttpServerClient(
            base_url="https://api.example.com",
            auth_type="none",
            auth_config={},
            pagination_config={"pagination_type": "none"},
        )

        assert client.custom_headers == {}
