"""Shared test fixtures for Generic HTTP integration tests"""

from typing import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Fixture to mock the Ocean context initialization."""
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "base_url": "https://api.example.com",
            "auth_type": "bearer_token",
            "api_token": "test-token",
            "pagination_type": "offset",
            "page_size": "100",
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.cache_provider = AsyncMock()
        mock_ocean_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.fixture
def mock_event_context() -> Generator[MagicMock, None, None]:
    """Fixture to mock event context."""
    from port_ocean.context.event import event_context, EventContext

    mock_event = MagicMock(spec=EventContext)
    mock_event.resource_config = MagicMock()
    mock_event.attributes = {}

    token = event_context.set(mock_event)  # type: ignore[attr-defined]
    try:
        yield mock_event
    finally:
        event_context.reset(token)  # type: ignore[attr-defined]
