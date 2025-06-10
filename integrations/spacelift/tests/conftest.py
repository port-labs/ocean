import pytest
from unittest.mock import AsyncMock, MagicMock
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Fixture to mock the Ocean context initialization."""
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "spacelift_api_key_endpoint": "https://test.app.spacelift.io",
            "spacelift_api_key_id": "test_key_id",
            "spacelift_api_key_secret": "test_key_secret",
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.cache_provider = AsyncMock()
        mock_ocean_app.cache_provider.get.return_value = None

        # Mock the router properly
        mock_router = MagicMock()
        mock_ocean_app.router = mock_router

        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass
