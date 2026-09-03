from typing import List, TYPE_CHECKING
from port_ocean.exceptions.core import OceanAbortException
from port_ocean.exceptions.execution_manager import ActionExecutionError

if TYPE_CHECKING:
    from github.clients.rate_limiter.utils import RateLimitInfo


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


class GraphQLForbiddenFieldError(Exception):
    """Raised when GraphQL fields return 403 FORBIDDEN and need to be excluded."""

    def __init__(self, fields: set[str]):
        self.fields = fields
        super().__init__(f"Fields {fields} returned 403 FORBIDDEN")


class CheckRunsException(Exception):
    """Exception for check runs errors."""


class OrganizationConflictError(Exception):
    """Raised when both github_organization and github_multi_organizations are provided."""


class RepositoryDefaultBranchNotFoundException(ActionExecutionError):
    """Exception for default branch not found."""

    DEFAULT_STATUS_LABEL = "Default branch not found"


class InvalidActionParametersException(ActionExecutionError):
    """Exception for invalid action parameters."""

    DEFAULT_STATUS_LABEL = "Invalid action inputs"


class NoWorkflowRunsFoundException(ActionExecutionError):
    """Exception for workflow runs not found after dispatch."""

    DEFAULT_STATUS_LABEL = "Dispatched workflow could not be tracked"


class RateLimitException(Exception):
    """Raised when GitHub API rate limit is exceeded."""

    def __init__(self, rate_limit_info: "RateLimitInfo"):
        self.rate_limit_info = rate_limit_info
        super().__init__(
            f"Rate limit exceeded. Reset at {rate_limit_info.reset_time}. "
            f"Remaining: {rate_limit_info.remaining}/{rate_limit_info.limit}"
        )
