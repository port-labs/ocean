from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None | MagicMock:
    """Fixture to initialize the PortOcean context."""
    mock_app = MagicMock()
    mock_app.integration_config = {
        "bitbucket_server_url": "https://bitbucket.example.com",
        "bitbucket_username": "test_user",
        "bitbucket_password": "test_password",
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
    with patch("client.http_async_client", new=AsyncClient()) as mock_client:
        yield mock_client
