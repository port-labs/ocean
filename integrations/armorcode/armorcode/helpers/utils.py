from enum import Enum
from typing import NamedTuple, Optional


class ObjectKind(str, Enum):
    """Enumeration of ArmorCode object kinds."""

    PRODUCT = "product"
    SUB_PRODUCT = "sub-product"
    FINDING = "finding"


class IgnoredError(NamedTuple):
    """Represents an error that should be ignored during API requests."""

    status: int | str
    message: Optional[str] = None
