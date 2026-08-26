from dataclasses import dataclass
from pathlib import Path

from port_ocean.core.probe.models import ProbeMode


@dataclass
class ProbeConfig:
    path: str | Path = "."
    kinds: list[str] | None = None
    mode: ProbeMode = ProbeMode.SHALLOW
