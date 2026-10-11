from unittest.mock import AsyncMock, MagicMock, patch

import httpx
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
        "external_access_token",
        new_callable=lambda: property(lambda self: "external-token"),
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
        "external_access_token",
        new_callable=lambda: property(
            lambda self: (_ for _ in ()).throw(ValueError("Token not available"))
        ),
    ):
        # Act & Assert
        with pytest.raises(ValueError, match="Token not available"):
            client.get_refreshed_token()


def test_auth_client_get_refreshed_token_disabled() -> None:
    """Identity-propagated clients must not load the integration OAuth token."""
    client = AuthClient("user-token")
    client.disable_token_refresh()

    with patch.object(
        type(client),
        "external_access_token",
        new_callable=lambda: property(lambda self: "integration-oauth-token"),
    ):
        with pytest.raises(ValueError, match="Token refresh is disabled"):
            client.get_refreshed_token()


def test_refresh_request_auth_creds_uses_token_when_refresh_disabled() -> None:
    """When refresh is disabled, keep the fixed user token even if OAuth exists."""
    client = AuthClient("user-token")
    client.disable_token_refresh()
    request = httpx.Request("GET", "https://gitlab.example.com/api/v4/projects")

    with patch.object(
        type(client),
        "external_access_token",
        new_callable=lambda: property(lambda self: "integration-oauth-token"),
    ):
        refreshed = client.refresh_request_auth_creds(request)

    assert refreshed.headers["Authorization"] == "Bearer user-token"


def test_refresh_request_auth_creds_prefers_external_when_refresh_enabled() -> None:
    client = AuthClient("integration-token")
    request = httpx.Request("GET", "https://gitlab.example.com/api/v4/projects")

    with patch.object(
        type(client),
        "external_access_token",
        new_callable=lambda: property(lambda self: "integration-oauth-token"),
    ):
        refreshed = client.refresh_request_auth_creds(request)

    assert refreshed.headers["Authorization"] == "Bearer integration-oauth-token"
