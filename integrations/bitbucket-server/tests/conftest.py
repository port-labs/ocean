from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError


def _build_mock_ocean_app() -> MagicMock:
    mock_app = MagicMock()
    # Used by init_webhook_client() for callback URL construction
    mock_app.base_url = "https://app.example.com"

    # PortOceanContext.integration_config reads from app.config.integration.config
    mock_app.config.integration.config = {
        "bitbucket_username": "test_user",
        "bitbucket_password": "test_password",
        "bitbucket_base_url": "https://bitbucket.example.com",
        "bitbucket_webhook_secret": None,
        "bitbucket_is_version8_point7_or_older": False,
        "bitbucket_rate_limit_quota": 1000,
        "bitbucket_rate_limit_window": 3600,
    }
    return mock_app


def _initialize_ocean_context_for_collection() -> None:
    # Ensure Ocean context exists during test collection/import time.
    mock_app = _build_mock_ocean_app()
    try:
        initialize_port_ocean_context(mock_app)
    except PortOceanContextAlreadyInitializedError:
        pass


_initialize_ocean_context_for_collection()


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None | MagicMock:
    """Fixture to initialize the PortOcean context."""
    mock_app = _build_mock_ocean_app()
    try:
        initialize_port_ocean_context(mock_app)
    except PortOceanContextAlreadyInitializedError:
        # Context already initialized, ignore
        pass
    return None


@pytest.fixture
def mock_http_client() -> Generator[AsyncClient, None, None]:
    """Mock HTTP client for API requests."""
    with patch("client.http_async_client", new=AsyncClient()) as mock_client:
        yield mock_client
