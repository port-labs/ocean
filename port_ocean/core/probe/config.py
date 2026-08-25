from dataclasses import dataclass
from pathlib import Path


@dataclass
class ProbeConfig:
    path: str | Path = "."
    kinds: list[str] | None = None
