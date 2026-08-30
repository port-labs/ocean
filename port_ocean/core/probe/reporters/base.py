from abc import ABC, abstractmethod
from typing import Any, ClassVar

from port_ocean.core.probe.config import ProbeConfig
from port_ocean.core.probe.models import ProbeReportingMode


class ProbeReporter(ABC):
    mode: ClassVar[ProbeReportingMode]
    BY_MODE: ClassVar[dict[ProbeReportingMode, type["ProbeReporter"]]] = {}

    def __init__(self, config: ProbeConfig) -> None:
        self.config = config

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if "mode" in cls.__dict__:
            ProbeReporter.BY_MODE[cls.mode] = cls

    @abstractmethod
    def report(self, report: dict[str, Any]) -> None:
        """Publish one probe status report."""
