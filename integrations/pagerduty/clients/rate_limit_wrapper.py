"""PagerDuty rate limit wrapper (local limiter + Redis publish).

The per-minute quota is one Redis pool. ``RetryTransport`` waits on it before
each attempt. The analytics daily quota is a second pool that is only
published and read. Acquiring it would sleep until the daily reset.
"""

import time
from types import TracebackType
from typing import Optional

import httpx
from loguru import logger

from clients.rate_limiter import (
    PagerDutyDailyRateLimitExceededError,
    PagerDutyRateLimiter,
    RateLimitInfo,
    daily_quota_exhausted,
)
from port_ocean.rate_limiting.centralized_rate_limiter import CentralizedRateLimiter
from port_ocean.rate_limiting.models import CentralizedRateLimitState
from port_ocean.rate_limiting.pool_state import PoolRedisState
from port_ocean.rate_limiting.rate_limit_wrapper import RateLimitWrapper
from port_ocean.rate_limiting.utils import (
    active_centralized_rate_limiter,
    record_centralized_rate_limit,
    use_centralized_rate_limiting,
)

# Action runs pause below this many requests left. The local semaphore still
# pauses at 90% utilization on its own.
MIN_REMAINING_RATE_LIMIT_FOR_EXECUTE = 20

MINUTE_POOL = "minute"
DAILY_POOL = "daily"


def _header_int(headers: httpx.Headers, name: str) -> int | None:
    raw = headers.get(name)
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _quota(
    headers: httpx.Headers, prefix: str, now: float
) -> tuple[int, int, float] | None:
    """``ratelimit-*`` or ``daily-ratelimit-*``. Reset headers are seconds, not epochs."""
    limit = _header_int(headers, f"{prefix}ratelimit-limit")
    remaining = _header_int(headers, f"{prefix}ratelimit-remaining")
    reset_seconds = _header_int(headers, f"{prefix}ratelimit-reset")
    if limit is None or remaining is None or reset_seconds is None:
        return None
    return limit, remaining, now + reset_seconds


def _log_state(
    pool: str,
    state: CentralizedRateLimitState,
    context: str,
    now: float,
) -> None:
    remaining = state.remaining
    limit = state.limit
    reset_at = state.reset_at
    ratio = round(remaining / limit, 3) if limit and remaining is not None else None
    reset_in_seconds = round(reset_at - now, 3) if reset_at is not None else None
    logger.info(
        "PagerDuty centralized rate limit state "
        f"pool={pool} context={context} remaining={remaining} "
        f"limit={limit} ratio={ratio} reset_at={reset_at} "
        f"reset_in_seconds={reset_in_seconds} blocked_until={state.blocked_until}",
        pool=pool,
        context=context,
        remaining=remaining,
        limit=limit,
        ratio=ratio,
        reset_at=reset_at,
        reset_in_seconds=reset_in_seconds,
        blocked_until=state.blocked_until,
    )


async def _read_daily_pool() -> PoolRedisState | None:
    limiter: CentralizedRateLimiter | None = active_centralized_rate_limiter()
    if limiter is None:
        return None
    try:
        return await limiter.read_pool_state(DAILY_POOL)
    except Exception as error:
        logger.warning(
            "PagerDuty daily rate limit read failed; using the local snapshot",
            error=str(error),
        )
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

    async def check_daily_budget(self, endpoint: str) -> None:
        """Raise when an analytics call would spend an exhausted daily quota.

        Redis is read and not acquired. Sleeping here would block the pod
        until the daily reset. A window whose reset has already passed is
        treated as unknown so the next response can refresh it.
        """
        if not endpoint.startswith("analytics/"):
            return
        if use_centralized_rate_limiting():
            state = await _read_daily_pool()
            if state is not None and state.limit is not None:
                now = time.time()
                if state.remaining <= 0 and state.reset_at > now:
                    seconds = max(0, int(state.reset_at - now))
                    logger.warning(
                        "PagerDuty analytics daily quota exhausted "
                        f"({state.remaining}/{state.limit}); skipping {endpoint} "
                        f"until reset in {seconds}s."
                    )
                    raise PagerDutyDailyRateLimitExceededError(
                        "PagerDuty analytics daily quota exhausted; "
                        f"resets in {seconds}s."
                    )
                return
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
        self._limiter.update_rate_limits(response.headers, context)

    async def _notify_transport_rate_limit_retry(
        self, response: httpx.Response
    ) -> None:
        self._limiter.update_rate_limits(response.headers, "transport-retry")

    def _is_minute_rate_limit(self, response: httpx.Response) -> bool:
        """A 429 that should hold the per-minute pool.

        An analytics daily 429 still carries a healthy per-minute remaining.
        That response must not block REST calls.
        """
        if response.status_code != 429:
            return False
        if not daily_quota_exhausted(response.headers):
            return True
        remaining = _header_int(response.headers, "ratelimit-remaining")
        return remaining is not None and remaining <= 0

    def _parse_centralized_state(
        self, response: httpx.Response, context: str
    ) -> Optional[CentralizedRateLimitState]:
        now = time.time()
        parsed = _quota(response.headers, "", now)
        if parsed is None:
            return None
        limit, remaining, reset_at = parsed
        blocked_until = reset_at if self._is_minute_rate_limit(response) else None
        state = CentralizedRateLimitState(
            remaining=remaining,
            limit=limit,
            reset_at=reset_at,
            blocked_until=blocked_until,
        )
        _log_state(self.pool, state, context, now)
        return state

    def _daily_state(
        self, response: httpx.Response, context: str
    ) -> Optional[CentralizedRateLimitState]:
        now = time.time()
        parsed = _quota(response.headers, "daily-", now)
        if parsed is None:
            return None
        limit, remaining, reset_at = parsed
        state = CentralizedRateLimitState(
            remaining=remaining,
            limit=limit,
            reset_at=reset_at,
            blocked_until=None,
        )
        _log_state(DAILY_POOL, state, context, now)
        return state

    async def record_rate_limit_response(
        self, response: httpx.Response, *, context: str = "transport-retry"
    ) -> None:
        await super().record_rate_limit_response(response, context=context)
        if not use_centralized_rate_limiting():
            return
        daily = self._daily_state(response, context)
        if daily is None:
            return
        # Never a 429 block. ``is_rate_limited`` would set ``blocked_until``,
        # and acquiring this pool would sleep until the daily reset.
        await record_centralized_rate_limit(DAILY_POOL, daily, is_rate_limited=False)

    def _centralized_is_rate_limited(self, response: httpx.Response) -> bool:
        return self._is_minute_rate_limit(response)

    def _local_is_close_to_rate_limit(self) -> bool:
        info = self._limiter.rate_limit_info
        if info is None or info.limit == 0 or info.seconds_until_reset <= 0:
            return False
        return info.remaining < MIN_REMAINING_RATE_LIMIT_FOR_EXECUTE

    def _local_seconds_until_rate_limit_reset(self) -> float:
        info = self._limiter.rate_limit_info
        if info is None or not self._local_is_close_to_rate_limit():
            return 0.0
        return float(info.seconds_until_reset)
