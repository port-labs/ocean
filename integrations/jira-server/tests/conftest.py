import pytest
from unittest.mock import MagicMock, AsyncMock
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None | MagicMock:
    """Fixture to initialize the PortOcean context."""
    mock_app = MagicMock()
    mock_app.integration_config = {
        "jira_host": "https://jira.example.com",
        "server_url": "https://jira.example.com",
        "username": "test-user",
        "password": "test-password",
    }
    try:
        mock_app.cache_provider = AsyncMock()
        mock_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_app)
    except PortOceanContextAlreadyInitializedError:
        # Context already initialized, ignore
        pass
    return None
