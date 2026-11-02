"""Jira rate limit wrapper (local limiter + Redis publish)."""

import time
from datetime import datetime
from types import TracebackType
from typing import Optional
from urllib.parse import urlparse

import httpx
from loguru import logger

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

    async def on_response(self, response: httpx.Response) -> None:
        await self._limiter.on_response(response)

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

    def _explicit_reset_at(self, headers: httpx.Headers) -> float | None:
        raw = headers.get("x-ratelimit-reset")
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
        except (ValueError, TypeError):
            return None

    def _resolve_reset_at(self, headers: httpx.Headers, now: float) -> float:
        """Keep a real reset across the 200s that omit ``x-ratelimit-reset``.

        A response with no reset uses the last future reset this client saw.
        Otherwise it uses the local limiter's one-second window.
        """
        explicit = self._explicit_reset_at(headers)
        if explicit is not None:
            self._known_reset_at = explicit
            return explicit
        if self._known_reset_at is not None and self._known_reset_at > now:
            return self._known_reset_at
        reset_at = now + DEFAULT_RATE_LIMIT_WINDOW_SECONDS
        self._known_reset_at = reset_at
        return reset_at

    def _parse_centralized_state(
        self, response: httpx.Response, context: str
    ) -> Optional[CentralizedRateLimitState]:
        headers = response.headers
        info = self._limiter._parse_partial_rate_limit_headers(headers)
        now = time.time()
        is_limited = response.status_code == RATE_LIMIT_STATUS_CODE

        if info is None:
            if not is_limited or self._known_limit is None:
                return None
            limit = self._known_limit
            remaining = 0
        else:
            limit = info.limit
            remaining = info.remaining
            if limit:
                self._known_limit = limit

        if is_limited or headers.get("x-ratelimit-nearlimit") == "true":
            remaining = 0

        reset_at = self._resolve_reset_at(headers, now)
        blocked_until: float | None = None
        if is_limited:
            delay = self._limiter._parse_retry_after(headers)
            if delay is not None and delay >= 0:
                blocked_until = now + delay
                if blocked_until > reset_at:
                    reset_at = blocked_until
                    self._known_reset_at = reset_at

        state = CentralizedRateLimitState(
            remaining=remaining,
            limit=limit,
            reset_at=reset_at,
            blocked_until=blocked_until,
        )
        ratio = round(remaining / limit, 3) if limit else None
        reset_in_seconds = round(reset_at - now, 3)
        logger.info(
            "Jira centralized rate limit state "
            f"pool={self.pool} context={context} remaining={remaining} "
            f"limit={limit} ratio={ratio} reset_at={reset_at} "
            f"reset_in_seconds={reset_in_seconds} blocked_until={blocked_until}",
            pool=self.pool,
            context=context,
            remaining=remaining,
            limit=limit,
            ratio=ratio,
            reset_at=reset_at,
            reset_in_seconds=reset_in_seconds,
            blocked_until=blocked_until,
        )
        return state

    def _centralized_is_rate_limited(self, response: httpx.Response) -> bool:
        return response.status_code == RATE_LIMIT_STATUS_CODE

    def _local_is_close_to_rate_limit(self) -> bool:
        info = self._limiter._rate_limit_info
        if info is None:
            return False
        return info.remaining <= self._limiter._minimum_limit_remaining

    def _local_seconds_until_rate_limit_reset(self) -> float:
        return self._limiter.seconds_until_reset
