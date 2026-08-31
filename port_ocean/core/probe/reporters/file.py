import json
from datetime import UTC, datetime
from typing import Any, ClassVar

from port_ocean.core.probe import ProbeConfig
from port_ocean.core.probe.models import ProbeReportingMode
from port_ocean.core.probe.reporters.base import ProbeReporter

PROBE_REPORTS_DIRECTORY = "probe_reports"


class FileProbeReporter(ProbeReporter):
    mode: ClassVar[ProbeReportingMode] = ProbeReportingMode.FILE

    def __init__(self, config: ProbeConfig):
        super().__init__(config)
        self.timestamp: str = datetime.now(UTC).strftime("%Y%m%dT%H%M%S_%fZ")

    def report(self, report: dict[str, Any]) -> None:
        reports_directory = self.config.path / PROBE_REPORTS_DIRECTORY
        reports_directory.mkdir(parents=True, exist_ok=True)
        report_path = reports_directory / f"probe_report_{self.timestamp}.json"
        report_path.write_text(
            json.dumps(report, indent=2, default=str),
            encoding="utf-8",
        )
