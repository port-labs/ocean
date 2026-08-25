from dataclasses import dataclass, field
from datetime import datetime, timezone
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


@dataclass
class ProbeResult:
    probe_start: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    probe_end: datetime | None = None
    results: list[ProbeCheck] = field(default_factory=list)
