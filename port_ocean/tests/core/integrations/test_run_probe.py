from unittest.mock import AsyncMock, MagicMock

import pytest

from port_ocean.context.event import EventType, event
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.ocean_types import ProbeContext, ProbeResult
from port_ocean.exceptions.core import ModeNotSupportedException


@pytest.mark.asyncio
async def test_run_probe_invokes_handler_in_probe_context() -> None:
    captured_event_type: str | None = None

    async def handler() -> ProbeContext:
        nonlocal captured_event_type
        captured_event_type = event.event_type
        return ProbeContext()

    integration = MagicMock(spec=BaseIntegration)
    integration.event_strategy = {"on_probe": handler}

    result = await BaseIntegration.run_probe(integration)

    assert captured_event_type == EventType.ON_PROBE
    assert isinstance(result, ProbeContext)
    assert isinstance(result.result, ProbeResult)


@pytest.mark.asyncio
async def test_run_probe_requires_registered_handler() -> None:
    # Arrange
    integration = MagicMock()
    integration.event_strategy = {"on_probe": None}
    integration.context.config.integration.type = "github"

    # Act / Assert
    with pytest.raises(
        ModeNotSupportedException,
        match="github does not support probe mode",
    ):
        await BaseIntegration.run_probe(integration)


@pytest.mark.asyncio
async def test_run_probe_propagates_handler_errors() -> None:
    handler = AsyncMock(side_effect=RuntimeError("unreachable"))
    integration = MagicMock(spec=BaseIntegration)
    integration.event_strategy = {"on_probe": handler}

    with pytest.raises(RuntimeError, match="unreachable"):
        await BaseIntegration.run_probe(integration)
