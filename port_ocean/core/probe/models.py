from dataclasses import dataclass, field
from enum import StrEnum


class ProbeMode(StrEnum):
    SHALLOW = "shallow"


class ProbeStatus(StrEnum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    UNKNOWN = "UNKNOWN"


@dataclass
class ProbeCheck:
    """Represents a singular probe check performed on a specific kind x scope."""

    kind: str
    scopes: dict[str, str] = field(default_factory=dict)
    status: ProbeStatus = ProbeStatus.PENDING
    message: str | None = None
