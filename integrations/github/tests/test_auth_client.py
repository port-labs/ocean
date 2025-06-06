from unittest.mock import AsyncMock, MagicMock

import pytest

from integrations.github.integration.utils.auth import AuthClient
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Initialize mock Ocean context for all tests"""
    try:
        mock_app = MagicMock()
        mock_app.config.integration.config = {
            "base_url": "https://api.github.com",
            "personal_access_token": "test-token",
            "user_agent": "test-user-agent",
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
    user_agent = "test-user-agent"
    client = AuthClient(token, user_agent=user_agent)

    # Act
    headers = client.get_headers()

    # Assert
    assert headers == {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": user_agent,
    }


def test_auth_client_missing_token() -> None:
    """Test that a missing access token raises TokenNotFoundException"""
    with pytest.raises(Exception) as exc_info:
        AuthClient(access_token=None, user_agent="test-user-agent")
    assert "TokenNotFoundException" in str(type(exc_info.value))


def test_auth_client_missing_user_agent() -> None:
    """Test that a missing user agent raises UserAgentNotFoundException"""
    with pytest.raises(Exception) as exc_info:
        AuthClient(access_token="test-token", user_agent=None)
    assert "UserAgentNotFoundException" in str(type(exc_info.value))
