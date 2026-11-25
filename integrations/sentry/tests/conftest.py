from __future__ import annotations

from types import SimpleNamespace
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import suppress
import pytest

from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError


@pytest.fixture(autouse=True)
def mock_ocean_context() -> MagicMock:
    mock_app = MagicMock()
    mock_app.is_saas.return_value = False
    # Match real structure expected by ocean.integration_config
    mock_app.config.integration.config = {
        "sentry_host": "https://sentry.io",
        "sentry_token": "dummy-token",
        "sentry_organization": "dummy-org",
        "sentry_webhook_secret": "dummy-secret",
    }
    mock_app.integration_router = MagicMock()
    mock_app.port_client = MagicMock()
    with suppress(PortOceanContextAlreadyInitializedError):
        mock_app.cache_provider = AsyncMock()
        mock_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_app)
    return mock_app


@pytest.fixture(autouse=True)
def disable_centralized_rate_limiting() -> Generator[None, None, None]:
    """Unit tests exercise the local limiter; keep the centralized path off."""
    inactive = SimpleNamespace(centralized_rate_limiter=None)
    with (
        patch("port_ocean.rate_limiting.rate_limit_wrapper.ocean", inactive),
        patch("port_ocean.rate_limiting.utils.ocean", inactive),
    ):
        yield
