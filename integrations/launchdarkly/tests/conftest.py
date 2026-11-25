"""Pytest configuration and fixtures."""

from types import SimpleNamespace
from typing import Generator

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def _mock_ocean_context() -> Generator[None, None, None]:
    """Mock Port Ocean context so OceanAsyncClient can be used without initializing the app."""
    mock_ocean = MagicMock()
    mock_ocean.app.is_saas.return_value = False
    with patch("port_ocean.helpers.async_client.ocean", mock_ocean):
        yield


@pytest.fixture(autouse=True)
def disable_centralized_rate_limiting() -> Generator[None, None, None]:
    """Unit tests exercise the local limiter; keep the centralized path off."""
    inactive = SimpleNamespace(centralized_rate_limiter=None)
    with (
        patch("port_ocean.rate_limiting.rate_limit_wrapper.ocean", inactive),
        patch("port_ocean.rate_limiting.utils.ocean", inactive),
    ):
        yield
