from dataclasses import dataclass, field
from enum import StrEnum


class ProbeStatus(StrEnum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    UNKNOWN = "UNKNOWN"


@dataclass
class ProbeCheck:
    status: ProbeStatus = ProbeStatus.PENDING
    message: str | None = None
    kind: str | None = None
    scopes: dict[str, str] = field(default_factory=dict)
