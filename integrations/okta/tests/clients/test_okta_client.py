"""Tests for Okta client."""

import pytest
from typing import Any, AsyncGenerator, Dict, List
from unittest.mock import Mock, patch, AsyncMock

from okta.clients.http.client import OktaClient


class TestOktaClient:
    """Test cases for OktaClient."""

    @pytest.fixture
    def client(self) -> OktaClient:
        """Create a test client."""
        return OktaClient(
            okta_domain="test.okta.com",
            api_token="test_token",
            max_retries=3,
        )

    def test_client_initialization(self, client: OktaClient) -> None:
        """Test client initialization."""
        assert client.okta_domain == "test.okta.com"
        assert client.api_token == "test_token"
        assert client.max_retries == 3

    def test_base_url_property(self, client: OktaClient) -> None:
        """Test base URL property."""
        expected_url = "https://test.okta.com/api/v1"
        assert client.base_url == expected_url

    @pytest.mark.asyncio
    async def test_make_request_success(self, client: OktaClient) -> None:
        """Test successful API request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "test_user"}
        mock_response.headers = {}

        with patch(
            "port_ocean.utils.http_async_client.request",
            new=AsyncMock(return_value=mock_response),
        ):
            response = await client._make_request("/users")
            assert response.status_code == 200
            assert response.json() == {"id": "test_user"}

    @pytest.mark.asyncio
    async def test_make_request_retry_on_failure(self, client: OktaClient) -> None:
        """Test request retry on failure."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.headers = {}

        with patch(
            "port_ocean.utils.http_async_client.request",
            side_effect=Exception("Network error"),
        ):
            with pytest.raises(Exception):
                await client._make_request("/users")

    def test_get_next_link(self, client: OktaClient) -> None:
        """Test parsing of next link from Link header."""
        link_header = '<https://test.okta.com/api/v1/users?after=123>; rel="next"'
        next_url = client._get_next_link(link_header)
        assert next_url == "https://test.okta.com/api/v1/users?after=123"

    def test_get_next_link_no_next(self, client: OktaClient) -> None:
        """Test parsing when no next link exists."""
        link_header = '<https://test.okta.com/api/v1/users>; rel="self"'
        next_url = client._get_next_link(link_header)
        assert next_url is None

    @pytest.mark.asyncio
    async def test_send_paginated_request_users(self, client: OktaClient) -> None:
        """Test pagination helper yields pages for users resource."""
        mock_users_page1: List[Dict[str, Any]] = [{"id": "user1"}, {"id": "user2"}]
        mock_users_page2: List[Dict[str, Any]] = [{"id": "user3"}]

        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield mock_users_page1
            yield mock_users_page2

        with patch.object(
            client, "send_paginated_request", side_effect=mock_paginated_request
        ):
            users: List[Dict[str, Any]] = []
            async for user_batch in client.send_paginated_request("users"):
                users.extend(user_batch)

            assert len(users) == 3
            assert users[0]["id"] == "user1"
            assert users[1]["id"] == "user2"
            assert users[2]["id"] == "user3"
