"""Unit tests for the log probe reporter."""

from unittest.mock import MagicMock, patch

import pytest

from port_ocean.core.probe.config import ProbeConfig
from port_ocean.core.probe.reporters.log import LogProbeReporter


@patch("port_ocean.core.probe.reporters.log.logger")
@pytest.mark.asyncio
async def test_log_probe_reporter_logs_report(mock_logger: MagicMock) -> None:
    # Arrange
    reporter = LogProbeReporter(ProbeConfig())
    report = {
        "probe_id": "probe-1",
        "status": "IN_PROGRESS",
    }

    # Act
    await reporter.report(report)

    # Assert
    mock_logger.info.assert_called_once_with("Probe status report", probe_report=report)
