from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from port_ocean.core.probe import ProbeConfig, ProbeReportingMode
from port_ocean.core.probe.reporters import (
    FileProbeReporter,
    LogProbeReporter,
    PortProbeReporter,
    ProbeReporter,
)


@patch("port_ocean.core.probe.reporters.log.logger")
def test_log_reporter_logs_full_report(mock_logger: MagicMock) -> None:
    report = {"status": "IN_PROGRESS", "checks": []}

    LogProbeReporter(ProbeConfig()).report(report)

    mock_logger.info.assert_called_once_with(
        "Probe status report",
        probe_report=report,
    )


def test_file_reporter_writes_timestamped_json_report(tmp_path: Path) -> None:
    report = {
        "stage": "init",
        "probe_id": "probe-123",
        "status": "IN_PROGRESS",
    }

    FileProbeReporter(ProbeConfig(path=tmp_path)).report(report)

    reports = list((tmp_path / "probe_reports").glob("probe_report_*.json"))
    assert len(reports) == 1
    contents = reports[0].read_text(encoding="utf-8")
    assert '"stage": "init"' in contents
    assert '"probe_id": "probe-123"' in contents
    assert '"status": "IN_PROGRESS"' in contents


@patch("port_ocean.core.probe.reporters.port.logger")
def test_port_reporter_is_a_stub(mock_logger: MagicMock) -> None:
    report = {"status": "IN_PROGRESS"}

    PortProbeReporter(ProbeConfig()).report(report)

    mock_logger.debug.assert_called_once_with(
        "Port probe reporting is not implemented yet",
        probe_report=report,
    )


@pytest.mark.parametrize(
    ("mode", "reporter_type"),
    [
        (ProbeReportingMode.LOG, LogProbeReporter),
        (ProbeReportingMode.FILE, FileProbeReporter),
        (ProbeReportingMode.PORT, PortProbeReporter),
    ],
)
def test_reporter_is_selected_from_config_mode(
    mode: ProbeReportingMode,
    reporter_type: type[ProbeReporter],
    tmp_path: Path,
) -> None:
    config = ProbeConfig(path=tmp_path, reporting_mode=mode)

    reporter = ProbeReporter.BY_MODE[config.reporting_mode](config)

    assert isinstance(reporter, reporter_type)
    assert reporter.config is config
