"""Pytest configuration and fixtures."""

from typing import Generator
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _mock_ocean_context() -> Generator[None, None, None]:
    """Mock the Ocean context so client/processor code can be imported and used
    without booting the full Ocean application."""
    mock_ocean = MagicMock()
    mock_ocean.app.is_saas.return_value = False
    mock_ocean.integration_config = {
        "iq_server_url": "https://iq.example.com",
        "iq_username": "svc-port",
        "iq_user_token": "token",
        "webhook_secret": "",
    }
    with patch("port_ocean.utils.async_http.ocean", mock_ocean):
        yield
