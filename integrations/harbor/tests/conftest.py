"""Shared pytest fixtures for Harbor integration tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
from harbor.clients import HarborClient


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Initialize mock Ocean context for all tests."""
    mock_app = MagicMock()
    mock_app.integration_config = {
        "harborHost": "http://localhost:8081",
        "harborUsername": "admin",
        "harborPassword": "Harbor12345",
        "verifySsl": True,
    }
    try:
        mock_app.cache_provider = AsyncMock()
        mock_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_app)
    except PortOceanContextAlreadyInitializedError:
        pass
    return None


@pytest.fixture
def mock_http_client():
    """Create a mock HTTP client for testing."""
    return AsyncMock()


@pytest.fixture
def harbor_client(mock_http_client):
    """Create a HarborClient with mocked HTTP client."""
    client = HarborClient(
        harbor_host="http://localhost:8081",
        harbor_username="admin",
        harbor_password="Harbor12345",
    )
    client.http_client = mock_http_client
    return client
