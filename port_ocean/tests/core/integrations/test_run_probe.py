from unittest.mock import AsyncMock, MagicMock

import pytest

from port_ocean.context.event import EventType, event
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.ocean_types import IntegrationEventsCallbacks
from port_ocean.core.probe import ProbeContext, ProbeResult
from port_ocean.exceptions.core import ModeNotSupportedException


@pytest.mark.asyncio
async def test_run_probe_invokes_handler_in_probe_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_event_type: str | None = None
    finalize = MagicMock()
    fail = MagicMock()
    monkeypatch.setattr(ProbeContext, "finalize", finalize)
    monkeypatch.setattr(ProbeContext, "fail", fail)

    async def handler(context: ProbeContext) -> ProbeContext:
        nonlocal captured_event_type
        captured_event_type = event.event_type
        return context

    integration = MagicMock(spec=BaseIntegration)
    integration.event_strategy = IntegrationEventsCallbacks(on_probe=handler)

    result = await BaseIntegration.run_probe(integration, "probe-id")

    assert captured_event_type == EventType.ON_PROBE
    assert isinstance(result, ProbeContext)
    assert result.probe_id == "probe-id"
    assert isinstance(result.result, ProbeResult)
    finalize.assert_called_once()
    fail.assert_not_called()


@pytest.mark.asyncio
async def test_run_probe_allows_a_local_run_without_probe_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    finalize = MagicMock()
    monkeypatch.setattr(ProbeContext, "finalize", finalize)

    async def handler(context: ProbeContext) -> ProbeContext:
        return context

    integration = MagicMock(spec=BaseIntegration)
    integration.event_strategy = IntegrationEventsCallbacks(on_probe=handler)

    result = await BaseIntegration.run_probe(integration)

    assert result.probe_id is None
    finalize.assert_called_once()


@pytest.mark.asyncio
async def test_run_probe_requires_registered_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    fail = MagicMock()
    finalize = MagicMock()
    monkeypatch.setattr(ProbeContext, "fail", fail)
    monkeypatch.setattr(ProbeContext, "finalize", finalize)
    integration = MagicMock()
    integration.event_strategy = IntegrationEventsCallbacks(on_probe=None)
    integration.context.config.integration.type = "github"

    # Act / Assert
    with pytest.raises(
        ModeNotSupportedException,
        match="github does not support probe mode",
    ):
        await BaseIntegration.run_probe(integration, "probe-id")

    fail.assert_called_once()
    finalize.assert_not_called()


@pytest.mark.asyncio
async def test_run_probe_propagates_handler_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fail = MagicMock()
    finalize = MagicMock()
    monkeypatch.setattr(ProbeContext, "fail", fail)
    monkeypatch.setattr(ProbeContext, "finalize", finalize)
    handler = AsyncMock(side_effect=RuntimeError("unreachable"))
    integration = MagicMock(spec=BaseIntegration)
    integration.event_strategy = IntegrationEventsCallbacks(on_probe=handler)

    with pytest.raises(RuntimeError, match="unreachable"):
        await BaseIntegration.run_probe(integration, "probe-id")

    fail.assert_called_once()
    finalize.assert_not_called()
