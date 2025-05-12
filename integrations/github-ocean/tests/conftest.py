import time
from typing import Any, Dict
from unittest.mock import MagicMock

import httpx
import pytest
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
from github.clients.client_factory import create_github_client


from github.clients.base_client import GithubClient

TEST_INTEGRATION_CONFIG: Dict[str, str] = {
    "github_token": "mock-github-token",
    "github_organization": "test-org",
    "github_host": "https://api.github.com",
    "webhook_secret": "test-secret",
}


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "github_token": TEST_INTEGRATION_CONFIG["github_token"],
            "github_organization": TEST_INTEGRATION_CONFIG["github_organization"],
            "github_host": TEST_INTEGRATION_CONFIG["github_host"],
            "webhook_secret": TEST_INTEGRATION_CONFIG["webhook_secret"],
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.base_url = ("https://baseurl.com",)

        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.fixture
def client(mock_ocean_context: Any) -> GithubClient:
    """Provide a GitHubClient instance with mocked Ocean context."""
    return create_github_client()


@pytest.fixture
def mock_http_response() -> MagicMock:
    """Provide a reusable mock HTTP response."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {
        "X-RateLimit-Remaining": "5000",
        "X-RateLimit-Reset": str(int(time.time()) + 3600),
    }
    return mock_response
