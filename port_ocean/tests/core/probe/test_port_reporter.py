"""Unit tests for the Port probe reporter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from port_ocean.core.probe.config import ProbeConfig
from port_ocean.core.probe.reporters.port import PortProbeReporter
from port_ocean.exceptions.probe import ProbeNotInitializedError


@patch("port_ocean.context.ocean.ocean")
@pytest.mark.asyncio
async def test_port_probe_reporter_patches_health_result(mock_ocean: MagicMock) -> None:
    # Arrange
    mock_ocean.port_client.get_org_id = AsyncMock(return_value="org-123")
    mock_ocean.port_client.patch_probe_health_result = AsyncMock()
    reporter = PortProbeReporter(ProbeConfig())
    report = {
        "probe_id": "probe-1",
        "status": "IN_PROGRESS",
        "checks": [],
    }

    # Act
    await reporter.report(report)

    # Assert
    mock_ocean.port_client.get_org_id.assert_called_once()
    mock_ocean.port_client.patch_probe_health_result.assert_called_once_with(
        "org-123",
        "probe-1",
        {"status": "IN_PROGRESS", "checks": []},
    )


@patch("port_ocean.context.ocean.ocean")
@pytest.mark.asyncio
async def test_port_probe_reporter_reuses_cached_org_id(
    mock_ocean: MagicMock,
) -> None:
    # Arrange
    mock_ocean.port_client.get_org_id = AsyncMock(return_value="org-123")
    mock_ocean.port_client.patch_probe_health_result = AsyncMock()
    reporter = PortProbeReporter(ProbeConfig())

    # Act
    await reporter.report({"probe_id": "probe-1", "status": "IN_PROGRESS"})
    await reporter.report({"probe_id": "probe-1", "status": "COMPLETED"})

    # Assert
    mock_ocean.port_client.get_org_id.assert_called_once()
    assert mock_ocean.port_client.patch_probe_health_result.call_count == 2
    mock_ocean.port_client.patch_probe_health_result.assert_any_call(
        "org-123",
        "probe-1",
        {"status": "IN_PROGRESS"},
    )
    mock_ocean.port_client.patch_probe_health_result.assert_any_call(
        "org-123",
        "probe-1",
        {"status": "COMPLETED"},
    )


@pytest.mark.asyncio
async def test_port_probe_reporter_raises_when_probe_id_missing() -> None:
    # Arrange
    reporter = PortProbeReporter(ProbeConfig())

    # Act + Assert
    with pytest.raises(
        ProbeNotInitializedError,
        match="probe_id is required when using Port probe reporting mode",
    ):
        await reporter.report({"status": "IN_PROGRESS"})
