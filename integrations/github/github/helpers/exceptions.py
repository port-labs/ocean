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


class RateLimitExceededError(Exception):
    def __init__(self, resource: str, retries: int):
        super().__init__(f"Rate limit exceeded for {resource} after {retries} retries")
        self.resource = resource
        self.retries = retries
