import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
from bitbucket_cloud.webhook_processors.webhook_client import BitbucketWebhookClient
from bitbucket_cloud.base_client import BitbucketBaseClient


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None | MagicMock:
    """Fixture to initialize the PortOcean context."""
    mock_app = MagicMock()
    mock_app.integration_config = {
        "bitbucket_app_password": "test_password",
        "bitbucket_username": "test_user",
        "bitbucket_workspace": "test_workspace",
        "bitbucket_host_url": "https://api.bitbucket.org/2.0",
    }
    try:
        initialize_port_ocean_context(mock_app)
    except PortOceanContextAlreadyInitializedError:
        # Context already initialized, ignore
        pass
    return None


@pytest.fixture
def mock_http_client() -> AsyncClient:
    """Mock HTTP client for API requests."""
    return AsyncMock(spec=AsyncClient)


@pytest.fixture
def webhook_client_mock() -> BitbucketWebhookClient:
    """Create a mocked webhook client."""
    base_client = BitbucketBaseClient(
        workspace="test-workspace",
        host="https://api.bitbucket.org/2.0",
        username="test-user",
        app_password="test-password",
    )
    client = BitbucketWebhookClient(base_client=base_client, secret="test-secret")
    client = MagicMock(spec=BitbucketWebhookClient)
    return client
