import time
from typing import Any, Optional
from dataclasses import dataclass
from pydantic import BaseModel, Field


@dataclass
class RateLimitInfo:
    """Tracks GitLab rate limit state from response headers."""

    remaining: int
    reset_time: int
    limit: int

    @property
    def seconds_until_reset(self) -> int:
        """Calculate seconds until rate limit resets."""
        return max(0, self.reset_time - int(time.time()))

    @property
    def utilization_percentage(self) -> float:
        """Calculate percentage of rate limit used."""
        if self.limit == 0:
            return 0
        return ((self.limit - self.remaining) / self.limit) * 100


@dataclass
class GitLabRateLimiterConfig:
    """
    Configuration for the GitLabRateLimiter.

    Attributes:
        max_concurrent: Maximum number of concurrent in-flight requests.
    """

    max_concurrent: int = 10


class RateLimiterRequiredHeaders(BaseModel):
    """
    GitLab rate limit response headers.

    GitLab returns these headers on every API response:
    - RateLimit-Limit: Max requests per minute
    - RateLimit-Remaining: Requests left in current window
    - RateLimit-Reset: Unix timestamp when quota resets
    """

    ratelimit_limit: Optional[str] = Field(default=None, alias="ratelimit-limit")
    ratelimit_remaining: Optional[str] = Field(
        default=None, alias="ratelimit-remaining"
    )
    ratelimit_reset: Optional[str] = Field(default=None, alias="ratelimit-reset")

    class Config:
        populate_by_name = True


def has_exhausted_rate_limit_headers(headers: Any) -> bool:
    """
    Check if GitLab rate limit headers indicate exhausted quota.

    Args:
        headers: Response headers (dict-like object)

    Returns:
        True if rate limit is exhausted (remaining=0 and reset time present)
    """
    remaining = headers.get("ratelimit-remaining")
    reset = headers.get("ratelimit-reset")
    return remaining == "0" and reset is not None
