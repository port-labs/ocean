from enum import StrEnum
from typing import NamedTuple, Optional


class ObjectKind(StrEnum):
    """Enum for Checkmarx One resource kinds."""

    PROJECT = "project"
    SCAN = "scan"
    CONTAINERS = "containersec"
    KICS = "kics"
    SCA = "sca"
    SAST = "sast"
    API_SEC = "apisec"


ALLOWED_KINDS_FOR_SCAN_RESULT = [
    ObjectKind.SAST,
    ObjectKind.CONTAINERS,
    ObjectKind.KICS,
    ObjectKind.SCA,
]


class IgnoredError(NamedTuple):
    status: int | str
    message: Optional[str] = None
    type: Optional[str] = None
