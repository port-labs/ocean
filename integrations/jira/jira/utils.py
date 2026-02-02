from typing import NamedTuple, Optional


class IgnoredError(NamedTuple):
    """Represents an error that should be ignored (logged but not raised).

    Attributes:
        status: HTTP status code to match
        message: Human-readable message for logging
        type: Error type identifier (e.g., "FORBIDDEN", "NOT_FOUND")
    """

    status: int | str
    message: Optional[str] = None
    type: Optional[str] = None
