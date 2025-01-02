import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Generator

from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.ocean import Ocean
from port_ocean.context.event import event_context


@pytest.fixture(autouse=True)
def mock_ocean_context() -> Generator[None, None, None]:
    """Mock Ocean context for testing."""
    with patch("port_ocean.context.ocean.Ocean") as mock_ocean_app:
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.config = MagicMock()
        mock_ocean_app.config.integration.config = {
            "token": "xoxb-test-token",
        }
        yield None


@pytest.fixture
def mock_event_context() -> Generator[MagicMock, None, None]:
    """Mock event context for testing."""
    with patch("port_ocean.context.event.event_context") as mock_context:
        mock_context.return_value.__aenter__.return_value = MagicMock()
        mock_context.return_value.__aexit__.return_value = None
        yield mock_context


@pytest.fixture
def mock_slack_client() -> AsyncMock:
    """Create a mock Slack API client."""
    mock_client = AsyncMock()
    mock_client._request = AsyncMock()
    mock_client._request.return_value = {
        "ok": True,
        "channels": [{
            "id": "C123456",
            "name": "general",
            "is_archived": False,
            "created": 1622505600,
        }],
        "members": [{
            "id": "U123456",
            "name": "testuser",
            "real_name": "Test User",
            "email": "test@example.com",
        }],
        "response_metadata": {"next_cursor": ""}
    }
    return mock_client
