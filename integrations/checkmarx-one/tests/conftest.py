import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Generator

from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
from port_ocean.context.event import EventContext
from unittest.mock import patch


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Mock the PortOcean context to prevent initialization errors."""
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "checkmarx_base_url": "https://ast.checkmarx.net",
            "checkmarx_iam_url": "https://iam.checkmarx.net",
            "checkmarx_tenant": "test-tenant",
            "checkmarx_api_key": "test-api-key",
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.cache_provider = AsyncMock()
        mock_ocean_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.fixture
def mock_event_context() -> Generator[MagicMock, None, None]:
    mock_event = MagicMock(spec=EventContext)
    mock_event.event_type = "test_event"
    mock_event.trigger_type = "manual"
    mock_event.attributes = {}
    mock_event._deadline = 999999999.0
    mock_event._aborted = False

    with patch("port_ocean.context.event.event", mock_event):
        yield mock_event
