"""Harbor integration exceptions."""

from port_ocean.exceptions.core import OceanAbortException


class HarborAPIError(OceanAbortException):
    """Base exception for Harbor API errors."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class InvalidConfigurationError(OceanAbortException):
    """Raised when Harbor configuration is invalid."""


class MissingCredentialsError(OceanAbortException):
    """Raised when Harbor credentials are missing."""


class UnauthorizedError(HarborAPIError):
    """Raised when Harbor authentication fails (401)."""


class ForbiddenError(HarborAPIError):
    """Raised when Harbor access is forbidden (403)."""


class NotFoundError(HarborAPIError):
    """Raised when Harbor resource is not found (404)."""

    def __init__(self, resource: str):
        super().__init__(f"Harbor resource not found: {resource}", 404)
        self.resource = resource


class RateLimitError(HarborAPIError):
    """Raised when Harbor rate limit is exceeded (429)."""


class ServerError(HarborAPIError):
    """Raised when Harbor server returns 5xx error."""
