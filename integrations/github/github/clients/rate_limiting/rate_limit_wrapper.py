"""GitHub rate limit wrapper (local limiter + Redis publish)."""

from types import TracebackType
from typing import Literal, Optional

import httpx

from github.clients.rate_limiting.limiter import GitHubRateLimiter
from github.clients.rate_limiting.utils import (
    RateLimitInfo,
    RateLimiterRequiredHeaders,
    extract_graphql_rate_limit_info,
    is_graphql_rate_limit_response,
    is_rest_rate_limit_response,
)
from port_ocean.rate_limiting.models import CentralizedRateLimitState
from port_ocean.rate_limiting.rate_limit_wrapper import RateLimitWrapper

MIN_REMAINING_RATE_LIMIT_FOR_ACTIONS = 20


class GitHubRateLimitWrapper(RateLimitWrapper):
    def __init__(
        self,
        limiter: GitHubRateLimiter,
        pool: str,
        api_type: Literal["rest", "graphql"],
    ) -> None:
        super().__init__(pool)
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

    async def _notify_transport_rate_limit_retry(self, response: httpx.Response) -> None:
        await self._limiter.notify_rate_limited(response)

    @staticmethod
    def _state_from_headers(
        headers: RateLimiterRequiredHeaders,
    ) -> Optional[CentralizedRateLimitState]:
        if not (
            headers.x_ratelimit_limit
            and headers.x_ratelimit_remaining
            and headers.x_ratelimit_reset
        ):
            return None
        return CentralizedRateLimitState(
            remaining=int(headers.x_ratelimit_remaining),
            limit=int(headers.x_ratelimit_limit),
            reset_at=float(headers.x_ratelimit_reset),
        )

    def _parse_centralized_state(
        self, response: httpx.Response, context: str
    ) -> Optional[CentralizedRateLimitState]:
        if self._api_type == "rest":
            return self._state_from_headers(
                RateLimiterRequiredHeaders(**response.headers)
            )
        state = self._state_from_headers(RateLimiterRequiredHeaders(**response.headers))
        if state is not None:
            return state
        info = extract_graphql_rate_limit_info(response)
        if info is None:
            return None
        return CentralizedRateLimitState(
            remaining=info.remaining,
            limit=info.limit,
            reset_at=float(info.reset_time),
        )

    def _centralized_is_rate_limited(self, response: httpx.Response) -> bool:
        if self._api_type == "rest":
            return is_rest_rate_limit_response(response)
        return is_graphql_rate_limit_response(response)

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
