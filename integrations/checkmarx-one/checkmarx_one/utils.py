from enum import StrEnum
from typing import NamedTuple, Optional


class ObjectKind(StrEnum):
    """Enum for Checkmarx One resource kinds."""

    PROJECT = "project"
    SCAN = "scan"
    API_SEC = "api-security"
    SCA = "sca"
    CONTAINER_SECURITY = "container-security"


class IgnoredError(NamedTuple):
    status: int | str
    message: Optional[str] = None
    type: Optional[str] = None
