"""Pytest configuration and fixtures."""

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
