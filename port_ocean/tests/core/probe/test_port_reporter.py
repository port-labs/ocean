"""Unit tests for the Port probe reporter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from port_ocean.core.probe.config import ProbeConfig
from port_ocean.core.probe.context import ProbeContext
from port_ocean.core.probe.models import ProbeCheck, ProbeCheckStatus
from port_ocean.core.probe.reporters.port import PortProbeReporter
from port_ocean.exceptions.probe import ProbeNotInitializedError


@pytest.mark.asyncio
@patch("port_ocean.context.ocean.ocean")
async def test_port_probe_reporter_patches_health_result(mock_ocean: MagicMock) -> None:
    # Arrange
    mock_ocean.port_client.get_org_id = AsyncMock(return_value="org_123")
    mock_ocean.port_client.patch_probe_health_result = AsyncMock()
    reporter = PortProbeReporter(ProbeConfig())
    context = ProbeContext(probe_id="0191a2b3-c4d5-7000-8000-000000000001")
    context.checks = [
        ProbeCheck(
            kind="repository",
            scopes={"accountId": 123},
            status=ProbeCheckStatus.SUCCESS,
            message="All good",
        )
    ]

    # Act
    await reporter.report(context.build_request_body())

    # Assert
    mock_ocean.port_client.get_org_id.assert_awaited_once()
    mock_ocean.port_client.patch_probe_health_result.assert_awaited_once_with(
        "org_123",
        "0191a2b3-c4d5-7000-8000-000000000001",
        {
            "status": "IN_PROGRESS",
            "probeMode": "shallow",
            "startedAt": context.started_at.isoformat(),
            "endedAt": None,
            "message": None,
            "checks": [
                {
                    "kind": "repository",
                    "scopes": {"accountId": "123"},
                    "status": "SUCCESS",
                    "message": "All good",
                }
            ],
        },
    )


@pytest.mark.asyncio
async def test_port_probe_reporter_requires_probe_id() -> None:
    # Arrange
    reporter = PortProbeReporter(ProbeConfig())

    # Act / Assert
    with pytest.raises(
        ProbeNotInitializedError,
        match="probe_id is required when using Port probe reporting mode",
    ):
        await reporter.report(ProbeContext().build_request_body())
