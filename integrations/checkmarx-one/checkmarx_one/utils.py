from enum import StrEnum
from typing import NamedTuple, Optional


class ObjectKind(StrEnum):
    """Enum for Checkmarx One resource kinds."""

    PROJECT = "project"
    SCAN = "scan"
    SCAN_RESULT = "scan_result"


class IgnoredError(NamedTuple):
    status: int | str
    message: Optional[str] = None
    type: Optional[str] = None
