"""Unit tests for BaseIntegration.run_probe."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.probe import ProbeConfig, ProbeContext, ProbeStatus
from port_ocean.exceptions.core import ModeNotSupportedException
from port_ocean.exceptions.probe import ProbeFailedError


@pytest.fixture
def integration() -> BaseIntegration:
    context = MagicMock()
    context.config.integration.type = "github"
    return BaseIntegration(context)


@patch("port_ocean.core.probe.context.get_spec_kinds", return_value=["repository"])
@pytest.mark.asyncio
async def test_run_probe_raises_when_listener_is_not_registered(
    mock_get_spec_kinds: MagicMock,
    integration: BaseIntegration,
) -> None:
    # Arrange
    integration.event_strategy.on_probe = None

    # Act / Assert
    with pytest.raises(
        ModeNotSupportedException,
        match="github does not support probe mode",
    ):
        await integration.run_probe("probe-123", ProbeConfig(path=Path("/integration")))

    mock_get_spec_kinds.assert_not_called()


@patch("port_ocean.core.probe.context.get_spec_kinds", return_value=["repository"])
@pytest.mark.asyncio
async def test_run_probe_finalizes_listener_context(
    mock_get_spec_kinds: MagicMock,
    integration: BaseIntegration,
) -> None:
    # Arrange
    async def on_probe(context: ProbeContext) -> ProbeContext:
        return context

    integration.event_strategy.on_probe = on_probe
    config = ProbeConfig(path=Path("/integration"), kinds=["repository"])

    # Act
    result = await integration.run_probe("probe-123", config)

    # Assert
    assert result.probe_id == "probe-123"
    assert result.status == ProbeStatus.COMPLETED
    assert result.ended_at is not None
    mock_get_spec_kinds.assert_called_once_with(Path("/integration"))


@patch("port_ocean.core.probe.context.get_spec_kinds", return_value=["repository"])
@pytest.mark.asyncio
async def test_run_probe_marks_context_failed_when_listener_raises(
    mock_get_spec_kinds: MagicMock,
    integration: BaseIntegration,
) -> None:
    # Arrange
    captured_context: list[ProbeContext] = []

    async def on_probe(context: ProbeContext) -> ProbeContext:
        captured_context.append(context)
        raise RuntimeError("probe failed")

    integration.event_strategy.on_probe = on_probe
    config = ProbeConfig(path=Path("/integration"), kinds=["repository"])

    # Act / Assert
    with pytest.raises(RuntimeError, match="probe failed"):
        await integration.run_probe("probe-123", config)

    assert captured_context[0].status == ProbeStatus.FAILED
    assert captured_context[0].ended_at is not None


@patch("port_ocean.core.probe.context.get_spec_kinds", return_value=["repository"])
@pytest.mark.asyncio
async def test_run_probe_raises_when_context_is_failed(
    mock_get_spec_kinds: MagicMock,
    integration: BaseIntegration,
) -> None:
    # Arrange
    captured_context: list[ProbeContext] = []
    message: str = "Probe failed"

    async def on_probe(context: ProbeContext) -> ProbeContext:
        captured_context.append(context)
        await context.fail(message)
        return context

    integration.event_strategy.on_probe = on_probe
    config = ProbeConfig(path=Path("/integration"), kinds=["repository"])

    # Act / Assert
    with pytest.raises(ProbeFailedError, match=message):
        await integration.run_probe("probe-123", config)

    assert captured_context[0].status == ProbeStatus.FAILED
    assert captured_context[0].message == message
