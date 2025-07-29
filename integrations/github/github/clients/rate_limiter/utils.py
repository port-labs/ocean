import time
import asyncio
from typing import Optional, Dict, Any, Literal, TypedDict
from dataclasses import dataclass
import httpx
from pydantic import BaseModel, Field
from loguru import logger

@dataclass
class PauseUntil:
    resume_at: Optional[float] = None

    def is_active(self) -> bool:
        return self.resume_at is not None and self.resume_at > time.time()

    def seconds_remaining(self) -> float:
        if self.resume_at is None:
            return 0.0
        return max(0.0, self.resume_at - time.time())

    def set(self, seconds_from_now: float) -> None:
        self.resume_at = time.time() + seconds_from_now

    def clear(self) -> None:
        self.resume_at = None


@dataclass
class RateLimitInfo:
    remaining: int
    reset_time: int
    limit: int

    @property
    def seconds_until_reset(self) -> int:
        return max(0, self.reset_time - int(time.time()))
    

@dataclass
class GitHubRateLimiterConfig:
    """
    Configuration for the GitHubRateLimiter.

    Attributes:
        api_type: Type of GitHub API being used ("rest", "graphql", "search").
        max_retries: Maximum number of retries on rate-limited requests.
        max_concurrent: Maximum number of concurrent in-flight requests.
    """
    api_type: Literal["rest", "graphql", "search"]
    max_concurrent: int
    max_retries: int = 5

class RateLimiterRequiredHeaders(BaseModel):
    """
    Headers required for the GitHubRateLimiter.
    """
    x_ratelimit_limit: Optional[str] = Field(alias="x-ratelimit-limit")
    x_ratelimit_remaining: Optional[str] = Field(alias="x-ratelimit-remaining")
    x_ratelimit_reset: Optional[str] = Field(alias="x-ratelimit-reset")

    def as_dict(self) -> Dict[str, str]:
        return self.dict(by_alias=True)
