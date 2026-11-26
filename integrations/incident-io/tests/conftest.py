from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from incident_io.clients.client_factory import ClientFactory

TEST_INTEGRATION_CONFIG: dict[str, Any] = {
    "incident_io_api_key": "inc_test",
    "incident_io_api_url": "https://api.incident.io",
}


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    try:
        mock_app = MagicMock()
        mock_app.integration_config = TEST_INTEGRATION_CONFIG
        mock_app.config.integration.config = TEST_INTEGRATION_CONFIG
        mock_app.cache_provider = AsyncMock()
        mock_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_app)
    except PortOceanContextAlreadyInitializedError:
        pass

    ClientFactory.clear()
