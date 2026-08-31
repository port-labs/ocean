"""Unit tests for the file probe reporter."""

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from port_ocean.core.probe.config import ProbeConfig
from port_ocean.core.probe.models import ProbeReportingMode
from port_ocean.core.probe.reporters.file import (
    PROBE_REPORTS_DIRECTORY,
    FileProbeReporter,
)


def test_file_probe_reporter_writes_report_to_configured_path(tmp_path: Path) -> None:
    # Arrange
    report = {
        "probe_id": "probe-1",
        "status": "IN_PROGRESS",
    }
    fixed_time = datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)

    # Act
    with patch(
        "port_ocean.core.probe.reporters.file.datetime",
        wraps=datetime,
    ) as mock_datetime:
        mock_datetime.now.return_value = fixed_time
        FileProbeReporter(
            ProbeConfig(path=tmp_path, reporting_mode=ProbeReportingMode.FILE)
        ).report(report)

    # Assert
    report_path = (
        tmp_path / PROBE_REPORTS_DIRECTORY / "probe_report_20260830T120000_000000Z.json"
    )
    assert report_path.exists()
    assert json.loads(report_path.read_text(encoding="utf-8")) == report


def test_file_probe_reporter_creates_reports_directory(tmp_path: Path) -> None:
    # Arrange
    reporter = FileProbeReporter(
        ProbeConfig(path=tmp_path, reporting_mode=ProbeReportingMode.FILE)
    )
    reports_directory = tmp_path / PROBE_REPORTS_DIRECTORY

    # Act
    reporter.report({"stage": "some_value"})

    # Assert
    assert reports_directory.is_dir()
    assert len(list(reports_directory.glob("probe_report_*.json"))) == 1
