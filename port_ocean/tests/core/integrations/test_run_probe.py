from unittest.mock import AsyncMock, MagicMock

import pytest

from port_ocean.context.event import EventType, event
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.probe import ProbeContext, ProbeResult
from port_ocean.exceptions.core import ModeNotSupportedException


@pytest.mark.asyncio
async def test_run_probe_invokes_handler_in_probe_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_event_type: str | None = None
    send_final_result = MagicMock()
    on_fatal_error = MagicMock()
    monkeypatch.setattr(ProbeContext, "send_final_result", send_final_result)
    monkeypatch.setattr(ProbeContext, "on_fatal_error", on_fatal_error)

    async def handler(context: ProbeContext) -> ProbeContext:
        nonlocal captured_event_type
        captured_event_type = event.event_type
        return context

    integration = MagicMock(spec=BaseIntegration)
    integration.event_strategy = {"on_probe": handler}

    result = await BaseIntegration.run_probe(integration)

    assert captured_event_type == EventType.ON_PROBE
    assert isinstance(result, ProbeContext)
    assert isinstance(result.result, ProbeResult)
    send_final_result.assert_called_once()
    on_fatal_error.assert_not_called()


@pytest.mark.asyncio
async def test_run_probe_requires_registered_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    on_fatal_error = MagicMock()
    send_final_result = MagicMock()
    monkeypatch.setattr(ProbeContext, "on_fatal_error", on_fatal_error)
    monkeypatch.setattr(ProbeContext, "send_final_result", send_final_result)
    integration = MagicMock()
    integration.event_strategy = {"on_probe": None}
    integration.context.config.integration.type = "github"

    # Act / Assert
    with pytest.raises(
        ModeNotSupportedException,
        match="github does not support probe mode",
    ):
        await BaseIntegration.run_probe(integration)

    on_fatal_error.assert_called_once()
    send_final_result.assert_not_called()


@pytest.mark.asyncio
async def test_run_probe_propagates_handler_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    on_fatal_error = MagicMock()
    send_final_result = MagicMock()
    monkeypatch.setattr(ProbeContext, "on_fatal_error", on_fatal_error)
    monkeypatch.setattr(ProbeContext, "send_final_result", send_final_result)
    handler = AsyncMock(side_effect=RuntimeError("unreachable"))
    integration = MagicMock(spec=BaseIntegration)
    integration.event_strategy = {"on_probe": handler}

    with pytest.raises(RuntimeError, match="unreachable"):
        await BaseIntegration.run_probe(integration)

    on_fatal_error.assert_called_once()
    send_final_result.assert_not_called()
