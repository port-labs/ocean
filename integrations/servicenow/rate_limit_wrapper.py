"""ServiceNow rate limit wrapper (local limiter + Redis publish)."""

import time
from types import TracebackType
from typing import Optional, Self
from urllib.parse import urlparse

import httpx
from port_ocean.rate_limiting.models import CentralizedRateLimitState
from port_ocean.rate_limiting.rate_limit_wrapper import RateLimitWrapper

from rate_limiter import (
    DEFAULT_429_COOLDOWN_SECONDS,
    LIMIT_HEADER,
    LIMIT_RESET_HEADER,
    RETRY_AFTER_HEADER,
    ServiceNowRateLimiter,
)


def centralized_rate_limit_pool(servicenow_url: str) -> str:
    """Redis pool for the integration credential on this ServiceNow instance."""
    parsed = urlparse(
        servicenow_url if "://" in servicenow_url else f"//{servicenow_url}"
    )
    return (parsed.hostname or servicenow_url).lower()


def _parse_float(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


class ServiceNowRateLimitWrapper(RateLimitWrapper):
    """Publishes ServiceNow's hourly rate limit rule to the shared pool.

    ServiceNow sends ``X-RateLimit-Limit`` and ``X-RateLimit-Reset`` but no
    remaining count. When a response reports a new window, the pool is reset
    to the full limit. Within a window, ``remaining`` is not published, so the
    Redis reserve script counts down each admitted request across pods.
    """

    def __init__(
        self,
        limiter: ServiceNowRateLimiter,
        pool: str,
        fallback_429_cooldown_seconds: float = DEFAULT_429_COOLDOWN_SECONDS,
    ) -> None:
        super().__init__(pool)
        self._limiter = limiter
        self._fallback_429_cooldown_seconds = float(fallback_429_cooldown_seconds)
        self._known_limit: int | None = None
        self._known_reset_at: float | None = None

    def is_rate_limit_response(self, response: httpx.Response) -> bool:
        return response.status_code == httpx.codes.TOO_MANY_REQUESTS

    # Local limiter

    async def __aenter__(self) -> Self:
        """Redis skips local quota accounting. ServiceNow has no in-flight cap."""
        if self._redis_admission_enabled():
            await self._local_acquire_concurrency()
            return self
        entered = await super().__aenter__()
        return entered

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        if self._redis_admission_enabled():
            await self._local_release_concurrency(exc_type, exc_val, exc_tb)
            return
        await super().__aexit__(exc_type, exc_val, exc_tb)

    async def _local_acquire(self) -> None:
        await self._limiter.__aenter__()

    async def _local_acquire_concurrency(self) -> None:
        return None

    async def _local_release(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        await self._limiter.__aexit__(exc_type, exc_val, exc_tb)

    async def _local_release_concurrency(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        del exc_type, exc_val, exc_tb

    async def _local_ingest_response(
        self, response: httpx.Response, context: str
    ) -> None:
        await self._limiter.update_from_response(response)

    async def _notify_transport_rate_limit_retry(
        self, response: httpx.Response
    ) -> None:
        await self._limiter.update_from_response(response)

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
        is_limited = self._centralized_is_rate_limited(response)
        limit = self._read_limit(headers)
        reset_at = _parse_float(headers.get(LIMIT_RESET_HEADER))
        if limit is None and reset_at is None and not is_limited:
            return None

        now = time.time()
        if is_limited:
            return CentralizedRateLimitState(
                remaining=0,
                limit=limit,
                reset_at=reset_at,
                blocked_until=self._blocked_until(headers, reset_at, now),
            )

        return CentralizedRateLimitState(
            remaining=self._remaining_for_new_window(limit, reset_at, now),
            limit=limit,
            reset_at=reset_at,
        )

    def _read_limit(self, headers: httpx.Headers) -> int | None:
        raw = _parse_float(headers.get(LIMIT_HEADER))
        if raw is None:
            return self._known_limit
        self._known_limit = int(raw)
        return self._known_limit

    def _remaining_for_new_window(
        self, limit: int | None, reset_at: float | None, now: float
    ) -> int | None:
        """Full quota when this response opens a window this pod has not seen.

        ``None`` inside a known window keeps the count Redis is decrementing.
        """
        if limit is None or reset_at is None or reset_at <= now:
            return None
        if self._known_reset_at is not None and reset_at <= self._known_reset_at:
            return None
        self._known_reset_at = reset_at
        return max(limit - 1, 0)

    def _blocked_until(
        self, headers: httpx.Headers, reset_at: float | None, now: float
    ) -> float:
        """``Retry-After``, else the window reset, else the local 429 cooldown."""
        retry_after = _parse_float(headers.get(RETRY_AFTER_HEADER))
        if retry_after is not None and retry_after >= 0:
            return now + retry_after
        if reset_at is not None and reset_at > now:
            return reset_at
        return now + self._fallback_429_cooldown_seconds
