from typing import Any, Generator
from unittest.mock import MagicMock, patch

import pytest
from port_ocean.context.ocean import initialize_port_ocean_context, ocean
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

TEST_INTEGRATION_CONFIG: dict[str, Any] = {
    "langfuse_host": "https://cloud.langfuse.com",
    "langfuse_public_key": "pk-test",
    "langfuse_secret_key": "sk-test",
    "webhook_secret": "whsec-test",
}


@pytest.fixture(autouse=True)
def mock_ocean_context() -> Generator[None, None, None]:
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = TEST_INTEGRATION_CONFIG
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.base_url = "https://baseurl.com"
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass

    with patch.dict(ocean.integration_config, TEST_INTEGRATION_CONFIG, clear=False):
        yield
