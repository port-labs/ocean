from unittest.mock import AsyncMock, MagicMock

import pytest

from port_ocean.context.event import EventType, event
from port_ocean.core.integrations.base import BaseIntegration


@pytest.mark.asyncio
async def test_run_probe_invokes_handler_in_probe_context() -> None:
    captured_event_type: str | None = None

    async def handler() -> None:
        nonlocal captured_event_type
        captured_event_type = event.event_type

    integration = MagicMock(spec=BaseIntegration)
    integration.event_strategy = {"on_probe": handler}

    await BaseIntegration.run_probe(integration)

    assert captured_event_type == EventType.ON_PROBE


@pytest.mark.asyncio
async def test_run_probe_requires_registered_handler() -> None:
    integration = MagicMock(spec=BaseIntegration)
    integration.event_strategy = {"on_probe": None}

    with pytest.raises(NotImplementedError, match="on_probe is not implemented"):
        await BaseIntegration.run_probe(integration)


@pytest.mark.asyncio
async def test_run_probe_propagates_handler_errors() -> None:
    handler = AsyncMock(side_effect=RuntimeError("unreachable"))
    integration = MagicMock(spec=BaseIntegration)
    integration.event_strategy = {"on_probe": handler}

    with pytest.raises(RuntimeError, match="unreachable"):
        await BaseIntegration.run_probe(integration)
