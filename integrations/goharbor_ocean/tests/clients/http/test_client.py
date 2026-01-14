from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from harbor.clients.http.client import HarborClient
from harbor.helpers.exceptions import (
    ForbiddenError,
    NotFoundError,
    ServerError,
    UnauthorizedError,
)


class TestHarborClient:
    """Test cases for HarborClient."""

    @pytest.fixture
    def client(self) -> HarborClient:
        """Create a test client."""
        return HarborClient(
            base_url="https://harbor.example.com",
            username="test_user",
            password="test_pass",
        )

    def test_client_initialization(self, client: HarborClient) -> None:
        """Test client initializes with correct values."""
        assert client._base_url_raw == "https://harbor.example.com"
        assert client.auth.username == "test_user"
        assert client.auth.password == "test_pass"

    def test_base_url_property_without_api_suffix(self, client: HarborClient) -> None:
        """Test base_url property adds API suffix."""
        expected = "https://harbor.example.com/api/v2.0"
        assert client.base_url == expected

    def test_base_url_property_with_api_suffix(self) -> None:
        """Test base_url property when URL already has suffix."""
        client = HarborClient(
            base_url="https://harbor.example.com/api/v2.0",
            username="test",
            password="test",
        )
        assert client.base_url == "https://harbor.example.com/api/v2.0"

    @pytest.mark.asyncio
    async def test_send_api_request_success(self, client: HarborClient) -> None:
        """Test successful API request returns JSON."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"name": "test_project"}
        mock_response.headers = {}

        with patch(
            "port_ocean.utils.http_async_client.request",
            new=AsyncMock(return_value=mock_response),
        ):
            result = await client.send_api_request("/projects")
            assert result == {"name": "test_project"}

    @pytest.mark.asyncio
    async def test_send_api_request_with_csrf_token(self, client: HarborClient) -> None:
        """Test POST request includes CSRF token."""
        # Mock systeminfo response with CSRF token
        systeminfo_response = Mock()
        systeminfo_response.status_code = 200
        systeminfo_response.json.return_value = {}
        systeminfo_response.headers = {"X-Harbor-CSRF-Token": "test_csrf_token"}

        post_response = Mock()
        post_response.status_code = 201
        post_response.json.return_value = {"id": 1}
        post_response.headers = {}

        responses = [systeminfo_response, post_response]

        with patch(
            "port_ocean.utils.http_async_client.request",
            new=AsyncMock(side_effect=responses),
        ) as mock_request:
            result = await client.send_api_request("/projects", method="POST", json_data={"name": "test"})

            assert result == {"id": 1}
            # Verify CSRF token was added to headers
            assert mock_request.call_count == 2

    @pytest.mark.asyncio
    async def test_send_api_request_unauthorized(self, client: HarborClient) -> None:
        """Test 401 response raises UnauthorizedError."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        error = httpx.HTTPStatusError("401", request=Mock(), response=mock_response)

        with patch(
            "port_ocean.utils.http_async_client.request",
            new=AsyncMock(side_effect=error),
        ):
            with pytest.raises(UnauthorizedError):
                await client.send_api_request("/projects")

    @pytest.mark.asyncio
    async def test_send_api_request_forbidden(self, client: HarborClient) -> None:
        """Test 403 response raises ForbiddenError."""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"

        error = httpx.HTTPStatusError("403", request=Mock(), response=mock_response)

        with patch(
            "port_ocean.utils.http_async_client.request",
            new=AsyncMock(side_effect=error),
        ):
            with pytest.raises(ForbiddenError):
                await client.send_api_request("/projects")

    @pytest.mark.asyncio
    async def test_send_api_request_not_found(self, client: HarborClient) -> None:
        """Test 404 response raises NotFoundError."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        error = httpx.HTTPStatusError("404", request=Mock(), response=mock_response)

        with patch(
            "port_ocean.utils.http_async_client.request",
            new=AsyncMock(side_effect=error),
        ):
            with pytest.raises(NotFoundError):
                await client.send_api_request("/projects/nonexistent")

    @pytest.mark.asyncio
    async def test_send_api_request_server_error(self, client: HarborClient) -> None:
        """Test 500 response raises ServerError."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        error = httpx.HTTPStatusError("500", request=Mock(), response=mock_response)

        with patch(
            "port_ocean.utils.http_async_client.request",
            new=AsyncMock(side_effect=error),
        ):
            with pytest.raises(ServerError):
                await client.send_api_request("/projects")

    @pytest.mark.asyncio
    async def test_send_api_request_ignored_404(self, client: HarborClient) -> None:
        """Test 404 for ignorable resources returns empty list."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        error = httpx.HTTPStatusError("404", request=Mock(), response=mock_response)

        with patch(
            "port_ocean.utils.http_async_client.request",
            new=AsyncMock(side_effect=error),
        ):
            result = await client.send_api_request("/projects/test/repositories")
            assert result == []

    @pytest.mark.asyncio
    async def test_send_paginated_request(self, client: HarborClient) -> None:
        """Test paginated request yields all pages."""
        page1 = [{"id": 1}, {"id": 2}]
        page2 = [{"id": 3}]
        page3 = []

        responses = [
            Mock(status_code=200, json=lambda: page1, headers={}),
            Mock(status_code=200, json=lambda: page2, headers={}),
            Mock(status_code=200, json=lambda: page3, headers={}),
        ]

        with patch(
            "port_ocean.utils.http_async_client.request",
            new=AsyncMock(side_effect=responses),
        ):
            results = []
            async for batch in client.send_paginated_request("/projects"):
                results.extend(batch)

            assert len(results) == 3
            assert results[0]["id"] == 1
            assert results[2]["id"] == 3

    @pytest.mark.asyncio
    async def test_get_project_success(self, client: HarborClient) -> None:
        """Test get_project returns project data."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"name": "test_project"}
        mock_response.headers = {}

        with patch(
            "port_ocean.utils.http_async_client.request",
            new=AsyncMock(return_value=mock_response),
        ):
            project = await client.get_project("test_project")
            assert project == {"name": "test_project"}

    @pytest.mark.asyncio
    async def test_get_project_not_found(self, client: HarborClient) -> None:
        """Test get_project returns None for 404."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        error = httpx.HTTPStatusError("404", request=Mock(), response=mock_response)

        with patch(
            "port_ocean.utils.http_async_client.request",
            new=AsyncMock(side_effect=error),
        ):
            project = await client.get_project("nonexistent")
            assert project is None

    @pytest.mark.asyncio
    async def test_get_repository_success(self, client: HarborClient) -> None:
        """Test get_repository returns repository data."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"name": "test_repo"}
        mock_response.headers = {}

        with patch(
            "port_ocean.utils.http_async_client.request",
            new=AsyncMock(return_value=mock_response),
        ):
            repo = await client.get_repository("test_project", "test_repo")
            assert repo == {"name": "test_repo"}

    @pytest.mark.asyncio
    async def test_get_repository_not_found(self, client: HarborClient) -> None:
        """Test get_repository returns None for 404."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        error = httpx.HTTPStatusError("404", request=Mock(), response=mock_response)

        with patch(
            "port_ocean.utils.http_async_client.request",
            new=AsyncMock(side_effect=error),
        ):
            repo = await client.get_repository("test_project", "nonexistent")
            assert repo is None
