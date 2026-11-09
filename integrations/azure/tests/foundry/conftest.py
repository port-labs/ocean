import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from port_ocean.context.ocean import initialize_port_ocean_context, ocean
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TEST_INTEGRATION_CONFIG: dict[str, Any] = {
    "azure_tenant_id": "tenant",
    "azure_client_id": "client",
    "azure_client_secret": "secret",
}


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = TEST_INTEGRATION_CONFIG
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.cache_provider = AsyncMock()
        mock_ocean_app.cache_provider.get.return_value = None
        mock_ocean_app.base_url = "https://example.com"
        mock_ocean_app.config.event_listener.should_process_webhooks = True
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass
    ocean.integration_config.update(TEST_INTEGRATION_CONFIG)
