import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Optional, Type

import httpx
from loguru import logger
from pydantic import BaseModel, Field


@dataclass
class RateLimitInfo:
    limit: int
    remaining: int
    seconds_until_reset: int

    @property
    def utilization_percentage(self) -> float:
        if self.limit <= 0:
            return 0.0
        used = self.limit - self.remaining
        return max(0.0, min(100.0, (used / self.limit) * 100.0))


class RateLimiterRequiredHeaders(BaseModel):
    """
    Headers required for the GitHubRateLimiter.
    """

    ratelimit_limit: Optional[str] = Field(alias="ratelimit-limit")
    ratelimit_remaining: Optional[str] = Field(alias="ratelimit-remaining")
    ratelimit_reset: Optional[str] = Field(alias="ratelimit-reset")

    def as_dict(self) -> Dict[str, str]:
        return self.dict(by_alias=True)


class PagerDutyRateLimiter:
    """
    Async rate limiter for PagerDuty APIs (REST and Analytics).
    - Controls concurrency via semaphore.
    - Tracks rate-limit headers and proactively sleeps when budget is depleted.
    - Computes retry delays on 429 using ratelimit-reset headers.
    """

    def __init__(self, max_concurrent: int = 10) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._lock = asyncio.Lock()

        self.rate_limit_info: Optional[RateLimitInfo] = None
        self._proactive_remaining_threshold = 1

    async def __aenter__(self) -> "PagerDutyRateLimiter":
        await self._semaphore.acquire()
        async with self._lock:
            if self.rate_limit_info and (
                self.rate_limit_info.remaining <= self._proactive_remaining_threshold
            ):
                sleep_seconds = self.rate_limit_info.seconds_until_reset
                if sleep_seconds > 0:
                    logger.warning(
                        f"PagerDuty requests paused for {sleep_seconds:.2f}s due to low remaining budget "
                        f"({self.rate_limit_info.remaining}/{self.rate_limit_info.limit})."
                    )
                    await asyncio.sleep(sleep_seconds)
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        self._semaphore.release()

    def _parse_rate_limit_headers(
        self, headers: RateLimiterRequiredHeaders
    ) -> Optional[RateLimitInfo]:
        if not (
            headers.ratelimit_limit
            and headers.ratelimit_remaining
            and headers.ratelimit_reset
        ):
            logger.warning(f"Rate limit headers not found: {headers}")
            return None

        return RateLimitInfo(
            limit=int(headers.ratelimit_limit),
            remaining=int(headers.ratelimit_remaining),
            seconds_until_reset=int(headers.ratelimit_reset),
        )

    async def update_rate_limits(
        self, headers: httpx.Headers, resource: str
    ) -> Optional[RateLimitInfo]:
        rate_limit_headers = RateLimiterRequiredHeaders(**headers)
        info = self._parse_rate_limit_headers(rate_limit_headers)
        if info:
            self.rate_limit_info = info
            logger.debug(
                f"Rate limit hit on {resource}: {info.remaining}/{info.limit} remaining "
                f"(resets in {info.seconds_until_reset}s)"
            )
        return info
