"""Jira rate limit wrapper (local limiter + Redis publish)."""

import time
from datetime import datetime
from types import TracebackType
from typing import Optional
from urllib.parse import urlparse

import httpx

from jira.rate_limiter import (
    DEFAULT_RATE_LIMIT_WINDOW_SECONDS,
    RATE_LIMIT_STATUS_CODE,
    JiraRateLimiter,
)
from port_ocean.rate_limiting.models import CentralizedRateLimitState
from port_ocean.rate_limiting.rate_limit_wrapper import RateLimitWrapper


def centralized_rate_limit_pool(jira_url: str) -> str:
    """Redis pool for the integration credential on this Jira site."""
    parsed = urlparse(jira_url if "://" in jira_url else f"//{jira_url}")
    return (parsed.hostname or jira_url).lower()


class JiraRateLimitWrapper(RateLimitWrapper):
    def __init__(self, limiter: JiraRateLimiter, pool: str) -> None:
        super().__init__(pool)
        self._limiter = limiter
        self._known_limit: int | None = None
        self._known_reset_at: float | None = None

    def is_rate_limit_response(self, response: httpx.Response) -> bool:
        return self._limiter.is_rate_limit_response(response)

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
        await self._limiter.on_response(response)

    async def _notify_transport_rate_limit_retry(
        self, response: httpx.Response
    ) -> None:
        await self._limiter.on_response(response)

    @property
    def _local_is_close_to_rate_limit(self) -> bool:
        info = self._limiter._rate_limit_info
        if info is None:
            return False
        return info.remaining <= self._limiter._minimum_limit_remaining

    @property
    def _local_seconds_until_rate_limit_reset(self) -> float:
        return self._limiter.seconds_until_reset

    # Centralized limiter

    def _centralized_is_rate_limited(self, response: httpx.Response) -> bool:
        return response.status_code == RATE_LIMIT_STATUS_CODE

    def _parse_centralized_state(
        self, response: httpx.Response, context: str
    ) -> Optional[CentralizedRateLimitState]:
        headers = response.headers
        is_limited = self._centralized_is_rate_limited(response)
        quota = self._read_quota(headers, is_limited)
        if quota is None:
            return None
        limit, remaining = quota

        now = time.time()
        reset_at = self._resolve_reset_at(headers, now)
        blocked_until = self._blocked_until(headers, now) if is_limited else None
        if blocked_until is not None and blocked_until > reset_at:
            reset_at = self._remember_reset(blocked_until)

        return CentralizedRateLimitState(
            remaining=remaining,
            limit=limit,
            reset_at=reset_at,
            blocked_until=blocked_until,
        )

    def _read_quota(
        self, headers: httpx.Headers, is_limited: bool
    ) -> tuple[int, int] | None:
        """Limit and remaining to publish, or ``None`` when there is nothing to publish.

        A 429 empties the quota. A 429 without quota headers reuses the last known limit.
        """
        info = self._limiter._parse_partial_rate_limit_headers(headers)
        if info is None:
            if not is_limited or self._known_limit is None:
                return None
            return self._known_limit, 0
        if info.limit:
            self._known_limit = info.limit
        return info.limit, 0 if is_limited else info.remaining

    def _blocked_until(self, headers: httpx.Headers, now: float) -> float | None:
        delay = self._limiter._parse_retry_after(headers)
        if delay is None or delay < 0:
            return None
        return now + delay

    def _resolve_reset_at(self, headers: httpx.Headers, now: float) -> float:
        """Keep a real reset across the 200s that omit ``x-ratelimit-reset``.

        A response with no reset uses the last future reset this client saw.
        Otherwise it uses the local limiter's one-second window.
        """
        explicit = self._explicit_reset_at(headers)
        if explicit is not None:
            return self._remember_reset(explicit)
        if self._known_reset_at is not None and self._known_reset_at > now:
            return self._known_reset_at
        return self._remember_reset(now + DEFAULT_RATE_LIMIT_WINDOW_SECONDS)

    def _explicit_reset_at(self, headers: httpx.Headers) -> float | None:
        raw = headers.get("x-ratelimit-reset")
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
        except (ValueError, TypeError):
            return None

    def _remember_reset(self, reset_at: float) -> float:
        self._known_reset_at = reset_at
        return reset_at
