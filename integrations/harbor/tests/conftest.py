from typing import Dict, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from port_ocean.context.event import EventContext
import pytest
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
from harbor.clients.auth.abstract_authenticator import AbstractHarborAuthenticator
from harbor.clients.auth.basic_authenticator import HarborBasicAuthenticator
from harbor.clients.auth.robot_authenticator import HarborRobotAuthenticator
from harbor.clients.http.harbor_client import HarborClient

TEST_INTEGRATION_CONFIG: Dict[str, str] = {
    "harbor_host": "http://localhost:8081",
    "username": "admin",
    "password": "Harbor12345",
    "robot_name": "test-robot",
    "robot_token": "test-robot-token",
}


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Mock the PortOcean context to prevent initialization errors."""

    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "harbor_host": TEST_INTEGRATION_CONFIG["harbor_host"],
            "username": TEST_INTEGRATION_CONFIG["username"],
            "password": TEST_INTEGRATION_CONFIG["password"],
            "robot_name": TEST_INTEGRATION_CONFIG["robot_name"],
            "robot_token": TEST_INTEGRATION_CONFIG["robot_token"],
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.base_url = "https://baseurl.com"
        mock_ocean_app.cache_provider = AsyncMock()
        mock_ocean_app.cache_provider.get.return_value = None

        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.fixture
def harbor_client() -> HarborClient:
    """Provide a HarborClient instance with test configuration."""
    # Reset singleton instance for testing
    HarborClient._instance = None

    # Mock the authenticator factory to avoid real authentication
    with patch(
        "harbor.clients.http.harbor_client.HarborAuthenticatorFactory"
    ) as mock_factory:
        mock_authenticator = MagicMock(spec=AbstractHarborAuthenticator)
        mock_authenticator.client = MagicMock()
        mock_factory.create.return_value = mock_authenticator

        client = HarborClient()
        return client


@pytest.fixture
def basic_authenticator() -> AbstractHarborAuthenticator:
    """Provide a HarborBasicAuthenticator instance."""
    return HarborBasicAuthenticator(
        username=TEST_INTEGRATION_CONFIG["username"],
        password=TEST_INTEGRATION_CONFIG["password"],
    )


@pytest.fixture
def robot_authenticator() -> AbstractHarborAuthenticator:
    """Provide a HarborRobotAuthenticator instance."""
    return HarborRobotAuthenticator(
        robot_name=TEST_INTEGRATION_CONFIG["robot_name"],
        robot_token=TEST_INTEGRATION_CONFIG["robot_token"],
    )


@pytest.fixture
def mock_http_response() -> MagicMock:
    """Provide a reusable mock HTTP response."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {
        "Content-Type": "application/json",
    }
    return mock_response


@pytest.fixture
def mock_event_context() -> Generator[MagicMock, None, None]:
    mock_event = MagicMock(spec=EventContext)
    mock_event.event_type = "test_event"
    mock_event.trigger_type = "manual"
    mock_event.attributes = {}
    mock_event._deadline = 999999999.0
    mock_event._aborted = False

    with patch("port_ocean.context.event.event", mock_event):
        yield mock_event
