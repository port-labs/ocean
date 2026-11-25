"""Sentry rate limit wrapper (local limiter + Redis publish)."""

import time
from types import TracebackType
from typing import Optional
from urllib.parse import urlparse

import httpx
from port_ocean.rate_limiting.models import CentralizedRateLimitState
from port_ocean.rate_limiting.rate_limit_wrapper import RateLimitWrapper

from .rate_limiter import SentryRateLimiter

LIMIT_HEADER = "X-Sentry-Rate-Limit-Limit"
REMAINING_HEADER = "X-Sentry-Rate-Limit-Remaining"
RESET_HEADER = "X-Sentry-Rate-Limit-Reset"
RETRY_AFTER_HEADER = "Retry-After"
DEFAULT_429_COOLDOWN_SECONDS = 60.0


def centralized_rate_limit_pool(sentry_base_url: str, organization: str) -> str:
    """Redis pool for this Sentry host and organization."""
    parsed = urlparse(
        sentry_base_url if "://" in sentry_base_url else f"//{sentry_base_url}"
    )
    host = parsed.hostname or sentry_base_url
    return f"{host}:{organization}".lower()


def _parse_float(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


class SentryRateLimitWrapper(RateLimitWrapper):
    """Publishes Sentry's per-response quota to the shared pool.

    Sentry limits each endpoint separately, but this client shares one pool
    per organization. Windows are a few seconds, so a backoff caused by another
    endpoint's count ends at the next reset.
    """

    def __init__(
        self,
        limiter: SentryRateLimiter,
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
        limit = _parse_float(headers.get(LIMIT_HEADER))
        remaining = _parse_float(headers.get(REMAINING_HEADER))
        reset_at = _parse_float(headers.get(RESET_HEADER))
        is_limited = self._centralized_is_rate_limited(response)
        if limit is None and remaining is None and reset_at is None and not is_limited:
            return None

        state_limit = int(limit) if limit is not None else None
        if is_limited:
            return CentralizedRateLimitState(
                remaining=0,
                limit=state_limit,
                reset_at=reset_at,
                blocked_until=self._blocked_until(headers, reset_at, time.time()),
            )
        return CentralizedRateLimitState(
            remaining=int(remaining) if remaining is not None else None,
            limit=state_limit,
            reset_at=reset_at,
        )

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
