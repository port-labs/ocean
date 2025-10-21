import time
from typing import Optional, Dict, Literal
from dataclasses import dataclass
from pydantic import BaseModel, Field


@dataclass
class RateLimitInfo:
    remaining: int
    reset_time: int
    limit: int

    @property
    def seconds_until_reset(self) -> int:
        return max(0, self.reset_time - int(time.time()))

    @property
    def utilization_percentage(self) -> float:
        return ((self.limit - self.remaining) / self.limit) * 100


@dataclass
class GitHubRateLimiterConfig:
    """
    Configuration for the GitHubRateLimiter.

    Attributes:
        api_type: Type of GitHub API being used ("rest", "graphql", "search").
        max_concurrent: Maximum number of concurrent in-flight requests.
    """

    api_type: Literal["rest", "graphql", "search"]
    max_concurrent: int


class RateLimiterRequiredHeaders(BaseModel):
    """
    Headers required for the GitHubRateLimiter.
    """

    x_ratelimit_limit: Optional[str] = Field(alias="x-ratelimit-limit")
    x_ratelimit_remaining: Optional[str] = Field(alias="x-ratelimit-remaining")
    x_ratelimit_reset: Optional[str] = Field(alias="x-ratelimit-reset")

    def as_dict(self) -> Dict[str, str]:
        return self.dict(by_alias=True)
