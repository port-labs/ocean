from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from contextlib import suppress
import pytest
from typing import Dict, Any

from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None | MagicMock:
    mock_app = MagicMock()
    # Match real structure expected by ocean.integration_config
    mock_app.config.integration.config = {
        "okta_domain": "example.okta.com",
        "okta_api_token": "dummy-token",
        "webhook_secret": "secret-123",
    }
    mock_app.integration_router = MagicMock()
    mock_app.port_client = MagicMock()
    with suppress(PortOceanContextAlreadyInitializedError):
        mock_app.cache_provider = AsyncMock()
        mock_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_app)
    return None


@pytest.fixture
def okta_event_payload_base() -> Dict[str, Any]:
    return {"data": {"events": []}}
