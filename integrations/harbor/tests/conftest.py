"""Shared fixtures for Harbor integration tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from harbor.clients.http.client import HarborClient


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Fixture to mock the Ocean context initialization."""
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config = MagicMock()
        mock_ocean_app.config.integration.config = {
            "base_url": "https://harbor.example.com",
            "username": "admin",
            "password": "password123",
            "api_version": "v2.0",
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
        username="test_user",
        password="test_password",
    )

