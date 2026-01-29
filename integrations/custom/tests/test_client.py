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
            merged_headers = {**client.custom_headers, **headers}
            captured_headers = merged_headers
            response = AsyncMock()
            response.json = AsyncMock(return_value={"data": []})
            response.raise_for_status = lambda: None
            return response

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
            merged_headers = {**client.custom_headers, **headers}
            captured_headers = merged_headers
            response = AsyncMock()
            response.json = AsyncMock(return_value={"data": []})
            response.raise_for_status = lambda: None
            return response

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


class TestMultipleHostsMode:
    """Test cases for multiple hosts mode"""

    def test_client_initialization_with_multiple_hosts_enabled(self) -> None:
        """Test client can be initialized with multiple_hosts enabled"""
        client = HttpServerClient(
            base_url="",
            auth_type="none",
            auth_config={},
            pagination_config={},
            multiple_hosts=True,
        )
        assert client.multiple_hosts is True
        assert client.base_url == ""

    def test_client_initialization_with_multiple_hosts_disabled(self) -> None:
        """Test client defaults to multiple_hosts disabled"""
        client = HttpServerClient(
            base_url="https://api.example.com",
            auth_type="none",
            auth_config={},
            pagination_config={},
        )
        assert client.multiple_hosts is False

    async def test_multiple_hosts_uses_full_url_as_endpoint(self) -> None:
        """Test that in multiple_hosts mode, the endpoint is used as the full URL"""
        client = HttpServerClient(
            base_url="",
            auth_type="none",
            auth_config={},
            pagination_config={"pagination_type": "none"},
            multiple_hosts=True,
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
            async for _ in client.fetch_paginated_data(
                endpoint="https://api.github.com/users"
            ):
                break

        assert captured_url == "https://api.github.com/users"

    async def test_multiple_hosts_with_http_url(self) -> None:
        """Test that http:// URLs work in multiple_hosts mode"""
        client = HttpServerClient(
            base_url="",
            auth_type="none",
            auth_config={},
            pagination_config={"pagination_type": "none"},
            multiple_hosts=True,
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
            async for _ in client.fetch_paginated_data(
                endpoint="http://localhost:8080/api/v1/users"
            ):
                break

        assert captured_url == "http://localhost:8080/api/v1/users"

    async def test_multiple_hosts_ignores_base_url(self) -> None:
        """Test that base_url is ignored in multiple_hosts mode"""
        client = HttpServerClient(
            base_url="https://should-be-ignored.com",
            auth_type="none",
            auth_config={},
            pagination_config={"pagination_type": "none"},
            multiple_hosts=True,
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
            async for _ in client.fetch_paginated_data(
                endpoint="https://api.different-host.com/v1/resources"
            ):
                break

        # Should use the endpoint URL directly, not combine with base_url
        assert captured_url == "https://api.different-host.com/v1/resources"

    async def test_multiple_hosts_raises_error_for_non_url_endpoint(self) -> None:
        """Test that non-URL endpoints raise an error in multiple_hosts mode"""
        client = HttpServerClient(
            base_url="",
            auth_type="none",
            auth_config={},
            pagination_config={"pagination_type": "none"},
            multiple_hosts=True,
        )

        with pytest.raises(ValueError, match="kind must be a full URL"):
            await client.fetch_paginated_data(endpoint="/api/v1/users").__anext__()

    async def test_multiple_hosts_raises_error_for_relative_path(self) -> None:
        """Test that relative paths raise an error in multiple_hosts mode"""
        client = HttpServerClient(
            base_url="",
            auth_type="none",
            auth_config={},
            pagination_config={"pagination_type": "none"},
            multiple_hosts=True,
        )

        with pytest.raises(ValueError, match="kind must be a full URL"):
            await client.fetch_paginated_data(endpoint="api/v1/users").__anext__()

    async def test_default_mode_still_works_with_multiple_hosts_false(self) -> None:
        """Test backward compatibility: default mode combines base_url + endpoint"""
        client = HttpServerClient(
            base_url="https://api.example.com",
            auth_type="none",
            auth_config={},
            pagination_config={"pagination_type": "none"},
            multiple_hosts=False,
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

        assert captured_url == "https://api.example.com/api/v1/users"

    async def test_default_mode_empty_base_url_raises_error(self) -> None:
        """Test that empty base_url raises error in default mode"""
        client = HttpServerClient(
            base_url="",
            auth_type="none",
            auth_config={},
            pagination_config={"pagination_type": "none"},
            multiple_hosts=False,
        )

        with pytest.raises(
            ValueError, match="base_url cannot be empty when multiple_hosts is disabled"
        ):
            await client.fetch_paginated_data(endpoint="/users").__anext__()

    async def test_multiple_hosts_with_query_params(self) -> None:
        """Test that query params work correctly in multiple_hosts mode"""
        client = HttpServerClient(
            base_url="",
            auth_type="none",
            auth_config={},
            pagination_config={"pagination_type": "none"},
            multiple_hosts=True,
        )

        captured_url: str | None = None
        captured_params: dict[str, Any] | None = None

        async def mock_make_request(
            url: str, method: str, params: dict[str, Any], headers: dict[str, str]
        ) -> AsyncMock:
            nonlocal captured_url, captured_params
            captured_url = url
            captured_params = params
            response = AsyncMock()
            response.json = AsyncMock(return_value={"data": []})
            response.raise_for_status = lambda: None
            return response

        with patch.object(client, "_make_request", mock_make_request):
            async for _ in client.fetch_paginated_data(
                endpoint="https://api.example.com/users",
                query_params={"limit": 100, "offset": 0},
            ):
                break

        assert captured_url == "https://api.example.com/users"
        assert captured_params == {"limit": 100, "offset": 0}

    async def test_multiple_hosts_with_custom_headers(self) -> None:
        """Test that custom headers work correctly in multiple_hosts mode"""
        client = HttpServerClient(
            base_url="",
            auth_type="none",
            auth_config={},
            pagination_config={"pagination_type": "none"},
            multiple_hosts=True,
            custom_headers={"X-Custom-Header": "test-value"},
        )

        captured_headers: dict[str, str] | None = None

        async def mock_make_request(
            url: str, method: str, params: dict[str, Any], headers: dict[str, str]
        ) -> AsyncMock:
            nonlocal captured_headers
            merged_headers = {**client.custom_headers, **headers}
            captured_headers = merged_headers
            response = AsyncMock()
            response.json = AsyncMock(return_value={"data": []})
            response.raise_for_status = lambda: None
            return response

        with patch.object(client, "_make_request", mock_make_request):
            async for _ in client.fetch_paginated_data(
                endpoint="https://api.example.com/users"
            ):
                break

        assert captured_headers is not None
        assert captured_headers["X-Custom-Header"] == "test-value"
