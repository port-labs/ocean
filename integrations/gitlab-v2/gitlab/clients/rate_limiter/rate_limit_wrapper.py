"""GitLab rate limit wrapper (local limiter + Redis publish)."""

import time
from http import HTTPStatus
from types import TracebackType
from typing import Optional
from urllib.parse import urlparse

import httpx
from loguru import logger

from gitlab.clients.rate_limiter.limiter import GitLabRateLimiter
from gitlab.clients.rate_limiter.utils import (
    RateLimitInfo,
    RateLimiterRequiredHeaders,
)
from port_ocean.rate_limiting.models import CentralizedRateLimitState
from port_ocean.rate_limiting.rate_limit_wrapper import RateLimitWrapper

MIN_REMAINING_RATE_LIMIT_FOR_ACTIONS = 20


def centralized_rate_limit_pool(base_url: str) -> str:
    """Redis pool for the integration token on this GitLab host.

    Identity-propagated user tokens stay on the local limiter. They do not
    open a Redis hash and they do not write this pool.
    """
    parsed = urlparse(base_url if "://" in base_url else f"//{base_url}")
    return (parsed.hostname or base_url).lower()


class GitLabRateLimitWrapper(RateLimitWrapper):
    def __init__(self, limiter: GitLabRateLimiter, pool: str) -> None:
        super().__init__(pool)
        self._limiter = limiter

    @property
    def rate_limit_info(self) -> Optional[RateLimitInfo]:
        return self._limiter.rate_limit_info

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

    def _retry_after_seconds(self, headers: httpx.Headers) -> float | None:
        raw = headers.get("retry-after")
        if raw is None:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    def _info_from_response(self, response: httpx.Response) -> Optional[RateLimitInfo]:
        try:
            headers = RateLimiterRequiredHeaders(**dict(response.headers))
        except (TypeError, ValueError):
            return None
        return self._limiter._parse_rate_limit_headers(headers)

    def _parse_centralized_state(
        self, response: httpx.Response, context: str
    ) -> Optional[CentralizedRateLimitState]:
        info = self._info_from_response(response)
        if info is None:
            return None

        blocked_until: float | None = None
        if response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
            delay = self._retry_after_seconds(response.headers)
            if delay is not None and delay >= 0:
                blocked_until = time.time() + delay

        state = CentralizedRateLimitState(
            remaining=info.remaining,
            limit=info.limit,
            reset_at=float(info.reset_time),
            blocked_until=blocked_until,
        )
        ratio = (
            round(info.remaining / info.limit, 3)
            if info.limit and info.remaining is not None
            else None
        )
        reset_in_seconds = round(info.reset_time - time.time(), 3)
        logger.info(
            "GitLab centralized rate limit state "
            f"pool={self.pool} context={context} remaining={info.remaining} "
            f"limit={info.limit} ratio={ratio} reset_at={info.reset_time} "
            f"reset_in_seconds={reset_in_seconds} blocked_until={blocked_until}",
            pool=self.pool,
            context=context,
            remaining=info.remaining,
            limit=info.limit,
            ratio=ratio,
            reset_at=info.reset_time,
            reset_in_seconds=reset_in_seconds,
            blocked_until=blocked_until,
        )
        return state

    def _centralized_is_rate_limited(self, response: httpx.Response) -> bool:
        return response.status_code == HTTPStatus.TOO_MANY_REQUESTS

    def _local_is_close_to_rate_limit(self) -> bool:
        info = self._limiter.rate_limit_info
        if not info:
            return False
        return info.remaining < MIN_REMAINING_RATE_LIMIT_FOR_ACTIONS

    def _local_seconds_until_rate_limit_reset(self) -> float:
        info = self._limiter.rate_limit_info
        if not info:
            return 0.0
        return float(info.seconds_until_reset)
