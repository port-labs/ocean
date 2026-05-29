from enum import StrEnum
from typing import NamedTuple, Optional


class ObjectKind(StrEnum):
    PROJECT = "mend-project"
    SECURITY_FINDING = "sca-finding"


class IgnoredError(NamedTuple):
    status: int | str
    message: Optional[str] = None
    type: Optional[str] = None
