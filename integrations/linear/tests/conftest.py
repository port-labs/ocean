"""Pytest configuration and fixtures."""

from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.context.ocean import initialize_port_ocean_context, ocean
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from linear.client import LinearClient

TEST_INTEGRATION_CONFIG: dict[str, Any] = {
    "linear_api_key": "test-api-key",
}


@pytest.fixture(autouse=True)
def _mock_ocean_context() -> Generator[None, None, None]:
    """Mock Port Ocean context so OceanAsyncClient and JQ can run in tests."""
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = TEST_INTEGRATION_CONFIG
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.base_url = "https://baseurl.com"
        mock_ocean_app.is_saas.return_value = False

        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass

    ocean.integration_config["linear_api_key"] = TEST_INTEGRATION_CONFIG[
        "linear_api_key"
    ]

    with patch("port_ocean.helpers.async_client.ocean", ocean):
        yield


@pytest.fixture
def linear_client() -> LinearClient:
    mock_http = MagicMock()
    mock_http.headers = {}
    with patch("linear.client.http_async_client", mock_http):
        return LinearClient("test-api-key")
