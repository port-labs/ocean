import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
from typing import Generator
from unittest.mock import MagicMock, patch
from bitbucket_integration.webhook.webhook_client import BitbucketWebhookClient


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None | MagicMock:
    """Fixture to initialize the PortOcean context."""
    mock_app = MagicMock()
    mock_app.integration_config = {
        "bitbucket_app_password": "test_password",
        "bitbucket_username": "test_user",
        "bitbucket_workspace": "test_workspace",
    }
    try:
        initialize_port_ocean_context(mock_app)
    except PortOceanContextAlreadyInitializedError:
        # Context already initialized, ignore
        pass
    return None


@pytest.fixture
def mock_http_client() -> Generator[AsyncClient, None, None]:
    """Mock HTTP client for API requests."""
    with patch(
        "bitbucket_integration.client.http_async_client", new=AsyncClient()
    ) as mock_client:
        yield mock_client


@pytest.fixture
def webhook_client_mock() -> BitbucketWebhookClient:
    """Create a mocked webhook client."""
    client = BitbucketWebhookClient(
        workspace="test-workspace", username="test-user", app_password="test-password"
    )
    client = MagicMock(spec=BitbucketWebhookClient)
    return client