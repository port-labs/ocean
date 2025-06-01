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
        mock_app.cache_provider = AsyncMock()
        mock_app.cache_provider.get.return_value = None
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
    client = MagicMock(spec=BitbucketWebhookClient)
    client.secret = "test-secret"
    client.workspace = "test-workspace"
    client.base_url = "https://api.bitbucket.org/2.0"
    client.base_client = MagicMock(spec=BitbucketBaseClient)
    client.base_client.headers = {"Authorization": "Basic test-auth"}
    return client
