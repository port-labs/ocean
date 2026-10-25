"""Pytest configuration and fixtures."""

from collections.abc import Generator, Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.config.settings import PortSettings


@pytest.fixture(autouse=True)
def _mock_ocean_context() -> Generator[None, None, None]:
    """Mock Port Ocean context so the integration modules can run in tests."""
    mock_ocean = MagicMock()
    mock_ocean.app.is_saas.return_value = False
    mock_ocean.config.client_timeout = 60

    mock_manager = MagicMock()
    mock_manager.untrack = AsyncMock(return_value=False)
    mock_manager.track = AsyncMock(return_value=True)

    with (
        patch("port_ocean.helpers.async_client.ocean", mock_ocean, create=True),
        patch("clients.anthropic_client.ocean", mock_ocean, create=True),
        patch("stream_manager._manager", mock_manager),
    ):
        yield


@pytest.fixture(autouse=True)
def _port_mcp_test_context() -> Iterator[None]:
    mock_ocean = MagicMock()
    mock_ocean.config.port = PortSettings(
        client_id="id",
        client_secret="secret",
        base_url="https://api.getport.io",
    )
    with patch("actions.port_mcp_utils.ocean", mock_ocean):
        yield
