import asyncio
import time
from typing import Dict
from unittest.mock import MagicMock

import httpx
import pytest
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError


from client import GitHubClient

TEST_INTEGRATION_CONFIG: Dict[str, str] = {
    "token": "mock-github-token",
    "organization": "test-org",
    "webhook_base_url": "https://app.example.com",
    "github_api_version": "2022-11-28",
}


pytest_plugins = ["pytest_asyncio"]


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for asyncio tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "token": TEST_INTEGRATION_CONFIG["token"],
            "organization": TEST_INTEGRATION_CONFIG["organization"],
            "webhook_base_url": TEST_INTEGRATION_CONFIG["webhook_base_url"],
            "github_api_version": TEST_INTEGRATION_CONFIG["github_api_version"],
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.base_url = TEST_INTEGRATION_CONFIG["webhook_base_url"]

        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.fixture
def client(mock_ocean_context) -> GitHubClient:
    """Provide a GitHubClient instance with mocked Ocean context."""
    return GitHubClient.from_ocean_config()


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
