from dataclasses import dataclass, field
from enum import StrEnum


class ProbeMode(StrEnum):
    SHALLOW = "shallow"


class ProbeCheckStatus(StrEnum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    UNKNOWN = "UNKNOWN"


class ProbeStatus(StrEnum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ProbeReportStage(StrEnum):
    INIT = "init"
    UPDATE = "update"
    FINALIZE = "finalize"
    FAIL = "fail"


@dataclass
class ProbeCheck:
    """Represents a singular probe check performed on a specific kind x scope."""

    kind: str
    scopes: dict[str, str | int] = field(default_factory=dict)
    status: ProbeCheckStatus = ProbeCheckStatus.PENDING
    message: str | None = None
