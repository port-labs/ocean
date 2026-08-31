from dataclasses import dataclass
from pathlib import Path

from port_ocean.core.probe.models import ProbeMode, ProbeReportingMode


@dataclass
class ProbeConfig:
    path: Path = Path(".")
    """The runtime path of the process"""
    kinds: list[str] | None = None
    """A list of specific kinds to probe. If not supplied, the probe will run on all supported kinds."""
    mode: ProbeMode = ProbeMode.SHALLOW
    reporting_mode: ProbeReportingMode = ProbeReportingMode.LOG
