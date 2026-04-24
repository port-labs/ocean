from typing import NamedTuple


class IgnoredError(NamedTuple):
    """Represents an HTTP error that should be ignored (logged but not raised).

    When an API request returns a status code matching an IgnoredError,
    the error is logged as a warning and an empty dict is returned instead
    of raising an exception. This allows the integration to gracefully
    handle expected errors like permission issues.

    Attributes:
        status: HTTP status code to ignore (e.g., 400, 403, 404)
        message: Human-readable description of why this error is ignored
    """

    status: int
    message: str | None = None
