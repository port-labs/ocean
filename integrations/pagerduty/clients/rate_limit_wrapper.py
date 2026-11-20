"""PagerDuty rate limit wrapper (local limiter + Redis publish).

The per-minute quota is the Redis pool that ``RetryTransport`` waits on. The
analytics daily quota stays on the local limiter: acquiring it from Redis
would sleep until the daily reset.
"""

import time
from http import HTTPStatus
from types import TracebackType
from typing import Optional

import httpx

from clients.rate_limiter import (
    PagerDutyRateLimiter,
    RateLimitInfo,
    daily_quota_exhausted,
)
from port_ocean.rate_limiting.models import CentralizedRateLimitState
from port_ocean.rate_limiting.rate_limit_wrapper import RateLimitWrapper

MIN_REMAINING_RATE_LIMIT_FOR_ACTIONS = 20

MINUTE_POOL = "minute"


def _header_int(headers: httpx.Headers, name: str) -> int | None:
    raw = headers.get(name)
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


class PagerDutyRateLimitWrapper(RateLimitWrapper):
    def __init__(self, limiter: PagerDutyRateLimiter, pool: str = MINUTE_POOL) -> None:
        super().__init__(pool)
        self._limiter = limiter

    @property
    def rate_limit_info(self) -> Optional[RateLimitInfo]:
        return self._limiter.rate_limit_info

    @property
    def daily_rate_limit_info(self) -> Optional[RateLimitInfo]:
        return self._limiter.daily_rate_limit_info

    @daily_rate_limit_info.setter
    def daily_rate_limit_info(self, value: Optional[RateLimitInfo]) -> None:
        self._limiter.daily_rate_limit_info = value

    def update_rate_limits(
        self, headers: httpx.Headers, resource: str
    ) -> Optional[RateLimitInfo]:
        return self._limiter.update_rate_limits(headers, resource)

    def check_daily_budget(self, endpoint: str) -> None:
        self._limiter.check_daily_budget(endpoint)

    async def _local_acquire(self) -> None:
        await self._limiter.__aenter__()

    async def _local_release(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        await self._limiter.__aexit__(exc_type, exc_val, exc_tb)

    async def _local_ingest_response(
        self, response: httpx.Response, context: str
    ) -> None:
        # PagerDutyRetryTransport and PagerDutyClient.send_api_request already
        # feed the local limiter on every response, in both modes, so the
        # analytics daily snapshot stays current while Redis is on.
        return None

    async def _notify_transport_rate_limit_retry(
        self, response: httpx.Response
    ) -> None:
        self._limiter.update_rate_limits(response.headers, "transport-retry")

    def _parse_centralized_state(
        self, response: httpx.Response, context: str
    ) -> Optional[CentralizedRateLimitState]:
        limit = _header_int(response.headers, "ratelimit-limit")
        remaining = _header_int(response.headers, "ratelimit-remaining")
        reset_seconds = _header_int(response.headers, "ratelimit-reset")
        if limit is None or remaining is None or reset_seconds is None:
            return None

        reset_at = time.time() + reset_seconds
        return CentralizedRateLimitState(
            remaining=remaining,
            limit=limit,
            reset_at=reset_at,
            blocked_until=(
                reset_at if self._centralized_is_rate_limited(response) else None
            ),
        )

    def _centralized_is_rate_limited(self, response: httpx.Response) -> bool:
        """A 429 that should block the per-minute pool.

        An analytics daily 429 still carries a healthy per-minute remaining
        and must not block REST calls.
        """
        if response.status_code != HTTPStatus.TOO_MANY_REQUESTS:
            return False
        if not daily_quota_exhausted(response.headers):
            return True
        remaining = _header_int(response.headers, "ratelimit-remaining")
        return remaining is not None and remaining <= 0

    @property
    def _local_is_close_to_rate_limit(self) -> bool:
        info = self._limiter.rate_limit_info
        if info is None or info.limit == 0 or info.seconds_until_reset <= 0:
            return False
        return info.remaining < MIN_REMAINING_RATE_LIMIT_FOR_ACTIONS

    @property
    def _local_seconds_until_rate_limit_reset(self) -> float:
        info = self._limiter.rate_limit_info
        if info is None or not self._local_is_close_to_rate_limit:
            return 0.0
        return float(info.seconds_until_reset)
