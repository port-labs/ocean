"""Pytest configuration and fixtures."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _mock_ocean_context() -> Generator[None, None, None]:
    """Mock Port Ocean context so OceanAsyncClient can run in tests."""
    mock_ocean = MagicMock()
    mock_ocean.app.is_saas.return_value = False
    with patch("port_ocean.helpers.async_client.ocean", mock_ocean, create=True):
        yield
