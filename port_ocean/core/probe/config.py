from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class ProbeMode(StrEnum):
    SHALLOW = "shallow"


@dataclass
class ProbeConfig:
    path: str | Path = "."
    kinds: list[str] | None = None
    mode: ProbeMode = ProbeMode.SHALLOW
