import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import AsyncClient, Response
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
from typing import Generator, Any, Dict, Optional
from github_cloud.initialize_client import init_client
import time


@pytest.fixture(autouse=True)
def mock_ocean_context() -> Optional[MagicMock]:
    """Fixture to initialize the PortOcean context."""
    mock_app = MagicMock()
    mock_app.integration_config = {
        "github_app_token": "test_token",
        "github_app_id": "test_app_id",
        "github_app_secret": "test_app_secret",
    }
    try:
        initialize_port_ocean_context(mock_app)
    except PortOceanContextAlreadyInitializedError:
        pass
    return None


@pytest.fixture
def rate_limit_state() -> Dict[str, Any]:
    """Track rate limit state across tests."""
    return {
        "total_limit": 5000,
        "remaining": 5000,
        "reset_time": int(time.time()) + 3600,
    }


@pytest.fixture
def mock_rate_limit_response(rate_limit_state: Dict[str, Any]) -> Dict[str, str]:
    """Create mock GitHub rate limit response headers."""
    # Decrease remaining count for each request
    rate_limit_state["remaining"] = max(0, rate_limit_state["remaining"] - 1)
    return {
        "X-RateLimit-Limit": str(rate_limit_state["total_limit"]),
        "X-RateLimit-Remaining": str(rate_limit_state["remaining"]),
        "X-RateLimit-Reset": str(rate_limit_state["reset_time"]),
        "X-RateLimit-Used": str(
            rate_limit_state["total_limit"] - rate_limit_state["remaining"]
        ),
        "X-RateLimit-Resource": "core",
    }


@pytest.fixture
def mock_response(mock_rate_limit_response: Dict[str, str]) -> Response:
    """Create a mock HTTP response."""
    response = MagicMock(spec=Response)
    response.status_code = 200
    response.json = AsyncMock()
    response.text = AsyncMock()
    response.headers = mock_rate_limit_response
    return response


@pytest.fixture
def mock_http_client(mock_response: Response) -> Generator[AsyncClient, None, None]:
    """Mock HTTP client for API requests."""
    with patch("client.http_async_client", new=AsyncClient()) as mock_client:
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.put = AsyncMock(return_value=mock_response)
        mock_client.delete = AsyncMock(return_value=mock_response)
        yield mock_client


@pytest.fixture
def mocked_github_client() -> MagicMock:
    """Create a mocked GitHub client."""
    client = MagicMock()
    client.get_single_resource = AsyncMock()
    client.get_repositories = AsyncMock()
    client.get_issues = AsyncMock()
    client.get_pull_requests = AsyncMock()
    client.get_teams = AsyncMock()
    client.get_workflows = AsyncMock()
    return client
