from typing import Any, ClassVar

from loguru import logger

from port_ocean.core.probe.models import ProbeReportingMode
from port_ocean.core.probe.reporters.base import ProbeReporter


class LogProbeReporter(ProbeReporter):
    mode: ClassVar[ProbeReportingMode] = ProbeReportingMode.LOG

    def report(self, report: dict[str, Any]) -> None:
        logger.info("Probe status report", probe_report=report)
