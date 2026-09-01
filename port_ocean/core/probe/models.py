from dataclasses import dataclass, field
from enum import StrEnum


class ProbeMode(StrEnum):
    SHALLOW = "shallow"


class ProbeReportingMode(StrEnum):
    LOG = "log"
    FILE = "file"
    PORT = "port"


class ProbeCheckStatus(StrEnum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    UNKNOWN = "UNKNOWN"


class ProbeStatus(StrEnum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class ProbeCheck:
    """Represents a singular probe check performed on a specific kind x scope."""

    kind: str
    scopes: dict[str, str | int] = field(default_factory=dict)
    status: ProbeCheckStatus = ProbeCheckStatus.PENDING
    message: str | None = None

    def serialize(self) -> dict[str, str | dict]:
        data = {
            "kind": self.kind,
            "scopes": self.scopes,
            "status": self.status,
        }

        if self.message:
            data["message"] = self.message

        return data
