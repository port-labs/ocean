"""LaunchDarkly rate limit wrapper (local limiter + Redis publish)."""

import time
from types import TracebackType
from typing import Optional
from urllib.parse import urlparse

import httpx
from port_ocean.rate_limiting.models import CentralizedRateLimitState
from port_ocean.rate_limiting.rate_limit_wrapper import RateLimitWrapper

from rate_limiter import LaunchDarklyRateLimiter

ROUTE_LIMIT_HEADER = "X-Ratelimit-Route-Limit"
ROUTE_REMAINING_HEADER = "X-Ratelimit-Route-Remaining"
GLOBAL_LIMIT_HEADER = "X-Ratelimit-Global-Limit"
GLOBAL_REMAINING_HEADER = "X-Ratelimit-Global-Remaining"
RESET_MS_HEADER = "X-Ratelimit-Reset"
RETRY_AFTER_HEADER = "Retry-After"
DEFAULT_429_COOLDOWN_SECONDS = 10.0


def centralized_rate_limit_pool(launchdarkly_url: str) -> str:
    """Redis pool for the LaunchDarkly account behind this host."""
    parsed = urlparse(
        launchdarkly_url if "://" in launchdarkly_url else f"//{launchdarkly_url}"
    )
    return (parsed.hostname or launchdarkly_url).lower()


def _parse_float(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


class LaunchDarklyRateLimitWrapper(RateLimitWrapper):
    """Publishes LaunchDarkly's ten-second quota to the shared pool.

    The route limit is used when the response carries one, else the account's
    global limit. Both reset every ten seconds, so a backoff caused by one
    route ends at the next window.
    """

    def __init__(
        self,
        limiter: LaunchDarklyRateLimiter,
        pool: str,
        fallback_429_cooldown_seconds: float = DEFAULT_429_COOLDOWN_SECONDS,
    ) -> None:
        super().__init__(pool)
        self._limiter = limiter
        self._fallback_429_cooldown_seconds = float(fallback_429_cooldown_seconds)

    def is_rate_limit_response(self, response: httpx.Response) -> bool:
        return response.status_code == httpx.codes.TOO_MANY_REQUESTS

    # Local limiter

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
        await self._limiter.update_from_headers(response.headers)

    async def _notify_transport_rate_limit_retry(
        self, response: httpx.Response
    ) -> None:
        await self._limiter.update_from_headers(response.headers)

    @property
    def _local_is_close_to_rate_limit(self) -> bool:
        return self._limiter.is_limit_reached

    @property
    def _local_seconds_until_rate_limit_reset(self) -> float:
        return self._limiter.seconds_until_reset

    # Centralized limiter

    def _centralized_is_rate_limited(self, response: httpx.Response) -> bool:
        return self.is_rate_limit_response(response)

    def _parse_centralized_state(
        self, response: httpx.Response, context: str
    ) -> Optional[CentralizedRateLimitState]:
        headers = response.headers
        limit, remaining = self._read_quota(headers)
        reset_ms = _parse_float(headers.get(RESET_MS_HEADER))
        reset_at = reset_ms / 1000.0 if reset_ms is not None else None
        is_limited = self._centralized_is_rate_limited(response)
        if limit is None and remaining is None and reset_at is None and not is_limited:
            return None

        if is_limited:
            return CentralizedRateLimitState(
                remaining=0,
                limit=limit,
                reset_at=reset_at,
                blocked_until=self._blocked_until(headers, reset_at, time.time()),
            )
        return CentralizedRateLimitState(
            remaining=remaining, limit=limit, reset_at=reset_at
        )

    @staticmethod
    def _read_quota(headers: httpx.Headers) -> tuple[int | None, int | None]:
        """Route limit when present, else the account's global limit."""
        for limit_header, remaining_header in (
            (ROUTE_LIMIT_HEADER, ROUTE_REMAINING_HEADER),
            (GLOBAL_LIMIT_HEADER, GLOBAL_REMAINING_HEADER),
        ):
            limit = _parse_float(headers.get(limit_header))
            remaining = _parse_float(headers.get(remaining_header))
            if limit is not None or remaining is not None:
                return (
                    int(limit) if limit is not None else None,
                    int(remaining) if remaining is not None else None,
                )
        return None, None

    def _blocked_until(
        self, headers: httpx.Headers, reset_at: float | None, now: float
    ) -> float:
        """``Retry-After``, else the window reset, else the fallback cooldown."""
        retry_after = _parse_float(headers.get(RETRY_AFTER_HEADER))
        if retry_after is not None and retry_after >= 0:
            return now + retry_after
        if reset_at is not None and reset_at > now:
            return reset_at
        return now + self._fallback_429_cooldown_seconds
