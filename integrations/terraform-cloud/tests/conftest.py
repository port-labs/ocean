from __future__ import annotations

from contextlib import suppress
from unittest.mock import AsyncMock, MagicMock

import pytest

from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    mock_app = MagicMock()
    mock_app.config.integration.config = {
        "terraform_cloud_host": "https://app.terraform.io",
        "terraform_cloud_token": "test-token",
        "webhook_secret": "test-secret",
    }
    mock_app.config.client_timeout = 30
    mock_app.integration_router = MagicMock()
    mock_app.port_client = MagicMock()
    with suppress(PortOceanContextAlreadyInitializedError):
        mock_app.cache_provider = AsyncMock()
        mock_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_app)
    return None
