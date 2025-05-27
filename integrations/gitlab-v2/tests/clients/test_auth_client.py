from unittest.mock import AsyncMock, MagicMock

import pytest
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from gitlab.clients.auth_client import AuthClient


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Initialize mock Ocean context for all tests"""
    try:
        mock_app = MagicMock()
        mock_app.config.integration.config = {
            "gitlab_url": "https://gitlab.example.com",
            "access_token": "test-token",
        }
        mock_app.cache_provider = AsyncMock()
        mock_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_app)
    except PortOceanContextAlreadyInitializedError:
        pass


def test_auth_client_headers() -> None:
    """Test authentication header generation"""
    # Arrange
    token = "test-token"
    client = AuthClient(token)

    # Act
    headers = client.get_headers()

    # Assert
    assert headers == {
        "Authorization": "Bearer test-token",
        "Content-Type": "application/json",
    }
