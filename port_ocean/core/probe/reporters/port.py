from typing import Any, ClassVar

from loguru import logger

from port_ocean.core.probe.models import ProbeReportingMode
from port_ocean.core.probe.reporters.base import ProbeReporter


class PortProbeReporter(ProbeReporter):
    mode: ClassVar[ProbeReportingMode] = ProbeReportingMode.PORT

    async def report(self, report: dict[str, Any]) -> None:
        """Placeholder for sending a probe status report to Port."""
        logger.debug(
            "Port probe reporting is not implemented yet",
            probe_report=report,
        )
