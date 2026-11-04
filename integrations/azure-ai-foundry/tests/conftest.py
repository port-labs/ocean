import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from port_ocean.context.ocean import initialize_port_ocean_context, ocean
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TEST_INTEGRATION_CONFIG: dict[str, Any] = {
    "foundry_project_endpoint": "https://acct.services.ai.azure.com/api/projects/demo",
    "api_version": "v1",
}


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = TEST_INTEGRATION_CONFIG
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.base_url = "https://example.com"
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass
    ocean.integration_config.update(TEST_INTEGRATION_CONFIG)
