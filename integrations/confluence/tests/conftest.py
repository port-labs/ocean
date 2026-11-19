from typing import Any
from unittest.mock import MagicMock

import pytest
from port_ocean.context.ocean import initialize_port_ocean_context, ocean
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

TEST_INTEGRATION_CONFIG: dict[str, Any] = {
    "confluence_host_url": "https://example.atlassian.net",
    "confluence_user_email": "docs@example.com",
    "confluence_api_token": "test-token",
}


def _apply_ocean_app(app: Any) -> None:
    app.config.integration.config = dict(TEST_INTEGRATION_CONFIG)
    app.config.client_timeout = 30.0
    app.integration_router = MagicMock()
    app.port_client = MagicMock()
    app.base_url = "https://baseurl.com"


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Provide a Port Ocean context without contacting Port."""
    mock_app = MagicMock()
    _apply_ocean_app(mock_app)
    try:
        initialize_port_ocean_context(mock_app)
    except PortOceanContextAlreadyInitializedError:
        _apply_ocean_app(ocean.app)

    from confluence.clients.client_factory import ClientFactory

    ClientFactory.clear()
