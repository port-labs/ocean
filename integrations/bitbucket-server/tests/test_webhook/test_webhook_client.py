from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from webhook_processors.webhook_client import BitbucketServerWebhookClient


@pytest.fixture
def mock_client() -> BitbucketServerWebhookClient:
    """Create a mocked Bitbucket Server client."""
    client = BitbucketServerWebhookClient(
        base_url="https://bitbucket.example.com",
        username="test-user",
        password="test-password",
        webhook_secret="test-secret",
        app_host="https://app.example.com",
    )
    client.client = MagicMock(spec=AsyncClient)
    return client


@pytest.mark.asyncio
async def test_is_version_8_point_7_and_older(
    mock_client: BitbucketServerWebhookClient,
) -> None:
    """Test version check functionality."""
    # Arrange
    mock_client._get_application_properties = AsyncMock(  # type: ignore[method-assign]
        return_value={"version": "8.7.0"}
    )

    # Act
    result = await mock_client.is_version_8_point_7_and_older()

    # Assert
    assert result is True


@pytest.mark.asyncio
async def test_setup_webhooks(mock_client: BitbucketServerWebhookClient) -> None:
    """Test webhook setup functionality."""
    # Arrange
    mock_client.is_version_8_point_7_and_older = AsyncMock(return_value=False)  # type: ignore[method-assign]
    mock_client.create_projects_webhook = AsyncMock()  # type: ignore[method-assign]

    # Act
    await mock_client.setup_webhooks({"TEST"})

    # Assert
    mock_client.create_projects_webhook.assert_called_once_with({"TEST"})


@pytest.mark.asyncio
async def test_verify_webhook_signature(
    mock_client: BitbucketServerWebhookClient,
) -> None:
    """Test webhook signature verification."""
    # Arrange
    mock_request = MagicMock()
    mock_request.headers = {"x-hub-signature": "sha256=test-signature"}
    mock_request.body = AsyncMock(return_value=b"test-body")

    # Act
    result = await mock_client.verify_webhook_signature(mock_request)

    # Assert
    assert isinstance(result, bool)
