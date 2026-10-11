from unittest.mock import MagicMock, patch

import pytest

from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.ocean import Ocean


@pytest.fixture
def ocean_app() -> Ocean:
    with patch("port_ocean.ocean.Ocean.__init__", return_value=None):
        app = Ocean()
        app.config = MagicMock()
        app.config.integration = MagicMock()
        app.config.integration.incremental_sync_enabled = False
        app.config.event_listener.should_resync = True
        context = PortOceanContext(app)
        app.integration = BaseIntegration(context)
        return app


async def _noop_resync_handler(kind: str) -> list[dict]:
    return []


def test_on_incremental_resync_skipped_when_incremental_sync_disabled(
    ocean_app: Ocean,
) -> None:
    context = PortOceanContext(ocean_app)
    ocean_app.config.integration.incremental_sync_enabled = False

    context.on_incremental_resync("repository")(_noop_resync_handler)

    assert ocean_app.integration.event_strategy.incremental.get("repository", []) == []


def test_on_incremental_resync_registers_when_incremental_sync_enabled(
    ocean_app: Ocean,
) -> None:
    context = PortOceanContext(ocean_app)
    ocean_app.config.integration.incremental_sync_enabled = True

    context.on_incremental_resync("repository")(_noop_resync_handler)

    handlers = ocean_app.integration.event_strategy.incremental.get("repository", [])
    assert len(handlers) == 1
    assert handlers[0] is _noop_resync_handler


def test_on_resync_still_registers_when_incremental_sync_disabled(
    ocean_app: Ocean,
) -> None:
    context = PortOceanContext(ocean_app)
    ocean_app.config.integration.incremental_sync_enabled = False

    context.on_resync("repository")(_noop_resync_handler)

    handlers = ocean_app.integration.event_strategy.resync.get("repository", [])
    assert len(handlers) == 1
    assert handlers[0] is _noop_resync_handler
