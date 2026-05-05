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


class PagerDutyDailyRateLimitExceededError(Exception):
    """Raised when an analytics request would exceed PagerDuty's daily quota."""


def daily_quota_exhausted(headers: httpx.Headers) -> bool:
    raw = headers.get("daily-ratelimit-remaining")
    try:
        return raw is not None and int(raw) <= 0
    except ValueError:
        return False


class RateLimiterRequiredHeaders(BaseModel):
    """Per-minute `ratelimit-*` headers and the analytics-only `daily-ratelimit-*` headers."""

    ratelimit_limit: Optional[str] = Field(alias="ratelimit-limit")
    ratelimit_remaining: Optional[str] = Field(alias="ratelimit-remaining")
    ratelimit_reset: Optional[str] = Field(alias="ratelimit-reset")
    daily_ratelimit_limit: Optional[str] = Field(alias="daily-ratelimit-limit")
    daily_ratelimit_remaining: Optional[str] = Field(alias="daily-ratelimit-remaining")
    daily_ratelimit_reset: Optional[str] = Field(alias="daily-ratelimit-reset")

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
        self._semaphore = asyncio.BoundedSemaphore(max_concurrent)
        self._lock = asyncio.Lock()
        self.rate_limit_info: Optional[RateLimitInfo] = None
        self.daily_rate_limit_info: Optional[RateLimitInfo] = None

    async def __aenter__(self) -> "PagerDutyRateLimiter":
        await self._semaphore.acquire()
        async with self._lock:
            # Sleep when rate limit is 90% used
            if (
                self.rate_limit_info
                and self.rate_limit_info.utilization_percentage >= 90
            ):
                sleep_seconds = self.rate_limit_info.seconds_until_reset
                if sleep_seconds > 0:
                    logger.warning(
                        f"PagerDuty requests paused for {sleep_seconds:.2f}s due to rate limit usage at "
                        f"{self.rate_limit_info.utilization_percentage:.1f}% "
                        f"({self.rate_limit_info.remaining}/{self.rate_limit_info.limit} remaining)."
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

    def _parse_per_minute_headers(
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

    def _parse_daily_headers(
        self, headers: RateLimiterRequiredHeaders
    ) -> Optional[RateLimitInfo]:
        if not (
            headers.daily_ratelimit_limit
            and headers.daily_ratelimit_remaining
            and headers.daily_ratelimit_reset
        ):
            return None
        return RateLimitInfo(
            limit=int(headers.daily_ratelimit_limit),
            remaining=int(headers.daily_ratelimit_remaining),
            seconds_until_reset=int(headers.daily_ratelimit_reset),
        )

    def update_rate_limits(
        self, headers: httpx.Headers, resource: str
    ) -> Optional[RateLimitInfo]:
        parsed = RateLimiterRequiredHeaders(**headers)

        info = self._parse_per_minute_headers(parsed)
        if info:
            self.rate_limit_info = info
            logger.debug(
                f"Rate limit on {resource}: {info.remaining}/{info.limit} remaining "
                f"(resets in {info.seconds_until_reset}s)"
            )

        daily_rate_limit_info = self._parse_daily_headers(parsed)
        if daily_rate_limit_info:
            self.daily_rate_limit_info = daily_rate_limit_info
            logger.debug(
                f"Daily rate limit on {resource}: {daily_rate_limit_info.remaining}/{daily_rate_limit_info.limit} "
                f"remaining (resets in {daily_rate_limit_info.seconds_until_reset}s)"
            )

        return info

    def check_daily_budget(self, endpoint: str) -> None:
        """Raise if a known-exhausted analytics daily quota would be hit. No-op for REST endpoints."""
        info = self.daily_rate_limit_info
        if not endpoint.startswith("analytics/") or info is None or info.remaining > 0:
            return

        logger.warning(
            f"PagerDuty analytics daily quota exhausted ({info.remaining}/{info.limit}); "
            f"skipping {endpoint} until reset in {info.seconds_until_reset}s."
        )
        raise PagerDutyDailyRateLimitExceededError(
            f"PagerDuty analytics daily quota exhausted; resets in {info.seconds_until_reset}s."
        )
