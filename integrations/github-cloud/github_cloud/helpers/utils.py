from enum import StrEnum
from dataclasses import dataclass

class ObjectKind(StrEnum):
    REPOSITORY="repository"
    ISSUE="issue"
    PULL_REQUEST="pull_request"
    TEAM="team"
    WORKFLOW="workflow"
    
@dataclass
class GithubRateLimiterConfig:
    """Github API Configuration for rate limiting."""

    LIMIT: int = 5000  # Number of requests allowed per window
    RESET_TIME: int = 3600  # Time window in seconds (default: 1 hour)
    remaining: int = 5000  # Remaining requests in the current window
