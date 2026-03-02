import time
from typing import Optional
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
        return (
            0 if self.limit == 0 else ((self.limit - self.remaining) / self.limit) * 100
        )


@dataclass
class GitLabRateLimiterConfig:
    max_concurrent: int = 10


class RateLimiterRequiredHeaders(BaseModel):
    ratelimit_limit: Optional[str] = Field(default=None, alias="ratelimit-limit")
    ratelimit_remaining: Optional[str] = Field(
        default=None, alias="ratelimit-remaining"
    )
    ratelimit_reset: Optional[str] = Field(default=None, alias="ratelimit-reset")
