"""GitHub rate limit wrapper (local limiter + Redis publish)."""

from types import TracebackType
from typing import Literal, Optional

import httpx

from github.clients.rate_limiter.limiter import GitHubRateLimiter
from github.clients.rate_limiter.utils import (
    RateLimitInfo,
    RateLimiterRequiredHeaders,
    extract_graphql_rate_limit_info,
)
from port_ocean.rate_limiting.models import CentralizedRateLimitState
from port_ocean.rate_limiting.rate_limit_wrapper import RateLimitWrapper

MIN_REMAINING_RATE_LIMIT_FOR_ACTIONS = 20


def github_centralized_rate_limit_pool(api_type: str, scope: str) -> str:
    """One Redis pool per GitHub API and credential.

    REST and GraphQL stay apart, and so do two installations of one app.
    """
    # scope is installation:{id}, app:{id}, or pat:{hash}. The Redis key is
    # ratelimit:{org}:{integration}:{pool}, so a colon in the scope would look
    # like another segment. installation:123 becomes installation-123, and the
    # pool is rest-installation-123.
    return f"{api_type}-{str(scope).replace(':', '-')}"


class GitHubRateLimitWrapper(RateLimitWrapper):
    def __init__(
        self,
        limiter: GitHubRateLimiter,
        pool: str,
        api_type: Literal["rest", "graphql", "search"],
        *,
        redis_enabled: bool = True,
    ) -> None:
        super().__init__(pool, redis_enabled=redis_enabled)
        self._limiter = limiter
        self._api_type = api_type

    @property
    def rate_limit_info(self) -> Optional[RateLimitInfo]:
        return self._limiter.rate_limit_info

    def is_rate_limit_response(self, response: httpx.Response) -> bool:
        return self._limiter.is_rate_limit_response(response)

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
        await self._limiter.on_response(response, context)

    async def _notify_transport_rate_limit_retry(
        self, response: httpx.Response
    ) -> None:
        await self._limiter.notify_rate_limited(response)

    @staticmethod
    def _centralized_state_from_info(
        info: RateLimitInfo,
    ) -> CentralizedRateLimitState:
        return CentralizedRateLimitState(
            remaining=info.remaining,
            limit=info.limit,
            reset_at=float(info.reset_time),
        )

    def _parse_centralized_state(
        self, response: httpx.Response, context: str
    ) -> Optional[CentralizedRateLimitState]:
        headers = RateLimiterRequiredHeaders(**response.headers)
        info = self._limiter._parse_rate_limit_headers(headers)
        if info is not None:
            return self._centralized_state_from_info(info)
        if self._api_type == "graphql":
            info = extract_graphql_rate_limit_info(response)
            if info is not None:
                return self._centralized_state_from_info(info)
        return None

    def _centralized_is_rate_limited(self, response: httpx.Response) -> bool:
        return self._limiter.is_rate_limit_response(response)

    @property
    def _local_is_close_to_rate_limit(self) -> bool:
        info = self._limiter.rate_limit_info
        if not info:
            return False
        return info.remaining < MIN_REMAINING_RATE_LIMIT_FOR_ACTIONS

    @property
    def _local_seconds_until_rate_limit_reset(self) -> float:
        info = self._limiter.rate_limit_info
        if not info:
            return 0.0
        return float(info.seconds_until_reset)
