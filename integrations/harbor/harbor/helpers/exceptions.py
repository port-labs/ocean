from port_ocean.exceptions.core import OceanAbortException


class AuthenticationException(OceanAbortException):
    """Base exception for authentication errors."""


class MissingConfiguration(OceanAbortException):
    """Raised when required configuration is missing."""


class MissingCredentials(AuthenticationException):
    """Raised when credentials are missing."""


class InvalidTokenException(AuthenticationException):
    """Raised when a token is invalid or expired."""
