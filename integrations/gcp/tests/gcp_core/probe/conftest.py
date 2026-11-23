from collections.abc import Callable
from typing import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest

import port_ocean.context.ocean as ocean_module
from port_ocean.context.ocean import PortOceanContext, initialize_port_ocean_context
from port_ocean.core.probe import ProbeContext


@pytest.fixture(autouse=True)
def mock_ocean_context() -> Generator[None, None, None]:
    """gcp_core modules read ocean.integration_config at import time."""
    mock_app = MagicMock()
    mock_app.config.integration.config = {"search_all_resources_per_minute_quota": 100}
    mock_app.cache_provider = AsyncMock()
    mock_app.cache_provider.get.return_value = None
    initialize_port_ocean_context(mock_app)

    yield

    ocean_module._port_ocean = PortOceanContext(None)


@pytest.fixture
def probe_context() -> ProbeContext:
    context = ProbeContext()
    context.reporter = MagicMock()
    context.reporter.report = AsyncMock()
    return context


@pytest.fixture
def install_client(monkeypatch: pytest.MonkeyPatch) -> Callable[[str, MagicMock], None]:
    """Pre-populate a singleton slot, as tests/gcp_core/search does."""

    def install(client_name: str, client: MagicMock) -> None:
        import gcp_core.clients as clients

        monkeypatch.setitem(clients._instances, client_name, client)

    return install
