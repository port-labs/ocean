import pytest
from unittest.mock import patch, MagicMock, AsyncMock

@pytest.fixture(autouse=True)
def mock_port_ocean():
    mock_app = MagicMock()
    mock_app.config = MagicMock()
    mock_app.config.client_timeout = 30
    mock_app.config.integration = MagicMock()
    mock_app.config.integration.config = {}

    with patch("port_ocean.context.ocean.ocean") as mock_ocean:
        mock_ocean.app = mock_app
        mock_ocean.integration_config = {
            "github_host": "https://api.github.com",
            "github_token": "test_token"
        }
        yield mock_ocean

@pytest.fixture(autouse=True)
def mock_http_client():
    mock_client = AsyncMock()
    with patch("port_ocean.utils.async_http._get_http_client_context", return_value=mock_client):
        yield mock_client
