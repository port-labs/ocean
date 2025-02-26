from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import Response, Request
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from bitbucket_integration.client import BitbucketClient


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Fixture to mock the Ocean context initialization."""
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "bitbucket_base_url": "https://api.bitbucket.org/2.0",
            "username": "test_user",
            "app_password": "test_password",
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.fixture
def mock_bitbucket_client() -> BitbucketClient:
    """Fixture to initialize BitbucketClient with mock parameters."""
    return BitbucketClient(username="test_user", app_password="test_password")


@pytest.mark.asyncio
async def test_generate_token(mock_bitbucket_client: BitbucketClient) -> None:
    """Test token generation."""
    assert mock_bitbucket_client.token is not None
    assert "Authorization" in mock_bitbucket_client.headers
    assert mock_bitbucket_client.headers["Authorization"].startswith("Basic")


@pytest.mark.asyncio
async def test_fetch_paginated_data_success(
    mock_bitbucket_client: BitbucketClient,
) -> None:
    """Test successful paginated data fetching."""
    mock_data = {"values": [{"id": 1}, {"id": 2}], "next": None}

    with patch.object(
        mock_bitbucket_client.http_client, "get", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = Response(
            200, request=Request("GET", "http://example.com"), json=mock_data
        )

        async for data in mock_bitbucket_client._fetch_paginated_data("test_endpoint"):
            assert data == mock_data["values"]

        mock_get.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_paginated_data_pagination(
    mock_bitbucket_client: BitbucketClient,
) -> None:
    """Test paginated data fetching with multiple pages."""
    page1_data = {"values": [{"id": 1}, {"id": 2}], "next": "http://example.com/page2"}
    page2_data = {"values": [{"id": 3}], "next": None}

    with patch.object(
        mock_bitbucket_client.http_client, "get", new_callable=AsyncMock
    ) as mock_get:
        mock_get.side_effect = [
            Response(
                200, request=Request("GET", "http://example.com"), json=page1_data
            ),
            Response(
                200, request=Request("GET", "http://example.com/page2"), json=page2_data
            ),
        ]

        results = []
        async for data in mock_bitbucket_client._fetch_paginated_data("test_endpoint"):
            results.extend(data)

        assert results == [{"id": 1}, {"id": 2}, {"id": 3}]
        assert mock_get.call_count == 2


@pytest.mark.asyncio
async def test_fetch_paginated_data_error(
    mock_bitbucket_client: BitbucketClient,
) -> None:
    """Test error handling in paginated data fetching."""
    with patch.object(
        mock_bitbucket_client.http_client, "get", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = Response(
            404,
            request=Request("GET", "http://example.com"),
            json={"error": "Not Found"},
        )

        async for data in mock_bitbucket_client._fetch_paginated_data("test_endpoint"):
            assert False, "Should not yield data on error"

        mock_get.assert_called_once()


@pytest.mark.asyncio
async def test_register_webhook(mock_bitbucket_client: BitbucketClient) -> None:
    """Test registering a webhook."""
    webhook_url = "https://example.com/webhook"
    secret = "test_secret"

    with patch.object(
        mock_bitbucket_client.http_client, "post", new_callable=AsyncMock
    ) as mock_post:
        mock_post.return_value = Response(
            200,
            request=Request("POST", "http://example.com"),
            json={"id": "webhook123"},
        )

        await mock_bitbucket_client.register_webhook("workspace1", webhook_url, secret)

        mock_post.assert_called_once_with(
            f"{mock_bitbucket_client.base_url}/workspaces/workspace1/hooks",
            json={
                "description": "Port Ocean Integration Webhook",
                "url": webhook_url,
                "active": True,
                "events": [
                    "repo:push",
                    "pullrequest:created",
                    "pullrequest:updated",
                    "pullrequest:fulfilled",
                    "pullrequest:rejected",
                ],
                "secret": secret,
            },
            headers=mock_bitbucket_client.headers,
        )
