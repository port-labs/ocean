from unittest.mock import MagicMock

import pytest
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from github.clients.auth_client import AuthClient


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Initialize mock Ocean context for all tests"""
    try:
        mock_app = MagicMock()
        mock_app.config.integration.config = {
            "github_host": "https://api.github.com",
            "github_token": "test-token",
        }
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
        "Authorization": "token test-token",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }
