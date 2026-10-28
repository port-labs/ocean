"""Azure DevOps rate limit wrapper (local limiter + Redis publish)."""

import time
from http import HTTPStatus
from types import TracebackType
from typing import Optional
from urllib.parse import urlparse

import httpx
from loguru import logger

from azure_devops.client.rate_limiter import (
    ADO_RATE_LIMIT_WINDOW_SECONDS,
    LIMIT_HEADER,
    LIMIT_REMAINING_HEADER,
    LIMIT_RESET_HEADER,
    LIMIT_RETRY_AFTER_HEADER,
    AzureDevOpsRateLimiter,
)
from azure_devops.misc import extract_org_name_from_url
from port_ocean.rate_limiting.models import CentralizedRateLimitState
from port_ocean.rate_limiting.rate_limit_wrapper import RateLimitWrapper


def centralized_rate_limit_pool(organization_url: str) -> str:
    """Redis pool for one Azure organization. That name is the VSID scope.

    dev, vsrm, and advsec hosts of the same organization share this pool.
    A value with ':' would split the Redis key, so an unrecognized URL falls
    back to its hostname label.
    """
    org_name = extract_org_name_from_url(organization_url.strip())
    if org_name and ":" not in org_name and "/" not in org_name:
        return org_name
    host = urlparse(organization_url).hostname or ""
    return host.split(".")[0] or org_name


class AzureDevOpsRateLimitWrapper(RateLimitWrapper):
    def __init__(
        self,
        limiter: AzureDevOpsRateLimiter,
        pool: str,
        *,
        redis_enabled: bool = True,
    ) -> None:
        super().__init__(pool, redis_enabled=redis_enabled)
        self._limiter = limiter

    async def signal_throttle(self, seconds: float, reason: str = "throttle") -> None:
        """Local cooldown for timeouts. Redis blocks only on a real 429."""
        await self._limiter.signal_throttle(seconds, reason)

    async def acquire(self) -> None:
        """Honor a timeout cooldown, then wait for Redis when it is on.

        ``acquire`` runs before every send. The local limiter only reads
        ``_throttle_until`` from its own ``__aenter__``, which Redis mode
        skips, so the wait lives here too. Local mode already waited on entry.
        """
        if self._redis_admission_enabled():
            await self._limiter.wait_out_throttle()
        await super().acquire()

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
        if response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
            await self._limiter.signal_throttle(
                ADO_RATE_LIMIT_WINDOW_SECONDS,
                reason="HTTP 429",
            )

    def _retry_after_seconds(self, headers: httpx.Headers) -> float:
        raw = headers.get(LIMIT_RETRY_AFTER_HEADER)
        if raw is None:
            return float(ADO_RATE_LIMIT_WINDOW_SECONDS)
        try:
            return float(raw)
        except ValueError:
            return float(ADO_RATE_LIMIT_WINDOW_SECONDS)

    def _parse_centralized_state(
        self, response: httpx.Response, context: str
    ) -> Optional[CentralizedRateLimitState]:
        headers = response.headers
        limit: int | None = None
        remaining: int | None = None
        reset_at: float | None = None
        try:
            limit_raw = headers.get(LIMIT_HEADER)
            remaining_raw = headers.get(LIMIT_REMAINING_HEADER)
            if limit_raw is not None and remaining_raw is not None:
                limit = int(limit_raw)
                remaining = int(remaining_raw)
            reset_raw = headers.get(LIMIT_RESET_HEADER)
            if reset_raw is not None:
                reset_at = float(reset_raw)
        except (TypeError, ValueError):
            limit = None
            remaining = None
            reset_at = None

        blocked_until: float | None = None
        if response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
            blocked_until = time.time() + self._retry_after_seconds(headers)

        if (
            limit is None
            and remaining is None
            and reset_at is None
            and blocked_until is None
        ):
            return None

        state = CentralizedRateLimitState(
            remaining=remaining,
            limit=limit,
            reset_at=reset_at,
            blocked_until=blocked_until,
        )
        ratio = round(remaining / limit, 3) if limit and remaining is not None else None
        reset_in_seconds = round(reset_at - time.time(), 3) if reset_at else None
        logger.info(
            "Azure DevOps centralized rate limit state "
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
        return response.status_code == HTTPStatus.TOO_MANY_REQUESTS

    def _local_is_close_to_rate_limit(self) -> bool:
        return self._limiter.is_close_to_limit

    def _local_seconds_until_rate_limit_reset(self) -> float:
        return self._limiter.seconds_until_reset
