"""Shared fixtures for Harbor integration tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from harbor.client import HarborClient


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Fixture to mock the Ocean context initialization."""
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config = MagicMock()
        mock_ocean_app.config.integration.config = {
            "base_url": "https://harbor.example.com",
            "verify_ssl": False,
            "auth_type": "basic",
            "username": "admin",
            "password": "password123",
            "pageSize": 100,
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.cache_provider = AsyncMock()
        mock_ocean_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.fixture
def mock_harbor_client() -> HarborClient:
    """Fixture to initialize HarborClient with mock parameters."""
    return HarborClient(
        base_url="https://harbor.example.com",
        verify_ssl=False,
        username="test_user",
        password="test_password",
    )


@pytest.fixture
def mock_harbor_client_no_auth() -> HarborClient:
    """Fixture to initialize HarborClient without authentication."""
    # Create a fresh client without credentials
    client = HarborClient(
        base_url="https://harbor.example.com",
        verify_ssl=False,
        username=None,
        password=None,
    )
    # Ensure auth is not set
    client.client.auth = None
    return client

