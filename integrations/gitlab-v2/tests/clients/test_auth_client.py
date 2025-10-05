from unittest.mock import AsyncMock, MagicMock, patch

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


def test_auth_client_get_refreshed_token() -> None:
    """Test getting refreshed external token"""
    # Arrange
    token = "test-token"
    client = AuthClient(token)

    # Mock the external_access_token property
    with patch.object(
        type(client),
        'external_access_token',
        new_callable=lambda: property(lambda self: "external-token")
    ):
        # Act
        refreshed_token = client.get_refreshed_token()

        # Assert
        assert refreshed_token == "external-token"


def test_auth_client_get_refreshed_token_raises_value_error() -> None:
    """Test that get_refreshed_token raises ValueError when external token is not available"""
    # Arrange
    token = "test-token"
    client = AuthClient(token)

    # Mock the external_access_token property to raise ValueError
    with patch.object(
        type(client),
        'external_access_token',
        new_callable=lambda: property(lambda self: (_ for _ in ()).throw(ValueError("Token not available")))
    ):
        # Act & Assert
        with pytest.raises(ValueError, match="Token not available"):
            client.get_refreshed_token()
