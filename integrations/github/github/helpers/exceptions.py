from typing import List
from port_ocean.exceptions.core import OceanAbortException


class AuthenticationException(OceanAbortException):
    """Base exception for authentication errors."""


class MissingCredentials(AuthenticationException):
    """Raised when credentials are missing."""


class InvalidTokenException(AuthenticationException):
    """Raised when a token is invalid or expired."""


class GraphQLClientError(Exception):
    """Exception raised for GraphQL API errors."""


class GraphQLErrorGroup(Exception):
    def __init__(self, errors: List[GraphQLClientError]):
        self.errors = errors
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        return "GraphQL errors occurred:\n" + "\n".join(f"- {e}" for e in self.errors)


class CheckRunsException(Exception):
    """Exception for check runs errors."""


class OrganizationRequiredException(Exception):
    """Raised when organization is required but not provided."""
