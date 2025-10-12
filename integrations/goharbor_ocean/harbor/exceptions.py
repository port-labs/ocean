"""
Contains contracts that maps to Harbor's Error object and our internal exceptions
raised in the library.
"""

# Maps to Harbor's Error object'
from typing import TypedDict, Optional
from port_ocean.exceptions.base import BaseOceanException


class Error(TypedDict):
    description: Optional[str]

    code: str
    """The error code"""

    message: str
    """ The error message"""

class Errors(TypedDict):
    errors: list[Error]
    """A list of errors"""


class HarborIntegrationException(BaseOceanException):
    """Base exception for Harbor integration errors"""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message, status_code)
        self.status_code = status_code


class InvalidConfigurationError(HarborIntegrationException):
    """Raised when the configuration provided is invalid"""

    def __init__(self, message: str = 'Invalid Harbor configuration provided') -> None:
        super().__init__(message)

class MissingCredentialsError(HarborIntegrationException):
    """Raised when credentials are missing in the configuration"""

    def __init__(self, message: str = 'Missing credentials - (username/password) are required') -> None:
        super().__init__(message)

class HarborAPIError(HarborIntegrationException):
    """Raised when Harbor API returns an error response"""

    def __init__(self, message: str, status_code: int, errors: list[Error] | None = None) -> None:
        super().__init__(message, status_code)
        self.errors = errors or []

class UnauthorizedError(HarborIntegrationException):
    """Raised when authentication to Harbor fails"""

    def __init__(self, message: str = 'Authentication failed. Check your Harbor credentials') -> None:
        super().__init__(message, status_code=401)

class ForbiddenError(HarborIntegrationException):
    """Raised when access to a Harbor resource is forbidden"""

    def __init__(self, message: str = 'Access to the requested Harbor resource is forbidden. Check your user permissions.') -> None:
        super().__init__(message, status_code=403)

class NotFoundError(HarborIntegrationException):
    """Raised when a requested resource is not found in Harbor"""

    def __init__(self, resource: str) -> None:
        message = f'Harbor resource not found: {resource}'
        super().__init__(message, status_code=404)

class RateLimitError(HarborIntegrationException):
    """Raised when the Harbor API rate limit is exceeded"""

    def __init__(self, retry_after: int | None = None) -> None:
        message = 'Rate limit exceeded. Please try again later.'
        if retry_after:
            message += f' Retry after {retry_after} seconds.'

        super().__init__(message, status_code=429)
        self.retry_after = retry_after

class ServerError(HarborIntegrationException):
    """Raised when Harbor API returns a server error"""

    def __init__(self, message: str = 'Harbor server error occurred', status_code: int = 500) -> None:
        super().__init__(message, status_code=status_code)

class WebhookSignatureError(HarborIntegrationException):
    """Raised when webhook signature verification fails"""

    def __init__(self, message: str = 'Invalid webhook signature') -> None:
        super().__init__(message)

class WebhookValidationError(HarborIntegrationException):
    """Raised when webhook payload validation fails"""

    def __init__(self, message: str = 'Invalid webhook payload') -> None:
        super().__init__(message)
