from abc import ABC, abstractmethod
from typing import Any, ClassVar

from port_ocean.core.probe.config import ProbeConfig
from port_ocean.core.probe.models import ProbeReportingMode


class ProbeReporter(ABC):
    mode: ClassVar[ProbeReportingMode]

    def __init__(self, config: ProbeConfig) -> None:
        self.config = config

    @abstractmethod
    async def report(self, report: dict[str, Any]) -> None:
        """Publish one probe status report."""
