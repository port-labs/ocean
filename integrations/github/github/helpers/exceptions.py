from port_ocean.exceptions.core import OceanAbortException


class AuthenticationException(OceanAbortException):
    """Base exception for authentication errors."""


class MissingCredentials(AuthenticationException):
    """Raised when credentials are missing."""


class InvalidTokenException(AuthenticationException):
    """Raised when a token is invalid or expired."""


class GraphQLClientError(Exception):
    """Exception raised for GraphQL API errors."""


class AdvancedSecurityNotEnabledError(Exception):
    """Exception raised when Advanced Security is not enabled for a repository."""


class DependabotDisabledError(Exception):
    """Exception raised when Dependabot is disabled for a repository."""
