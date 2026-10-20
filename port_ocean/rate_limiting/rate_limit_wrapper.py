"""Rate limit facade: local integration limiter vs cross-pod Redis."""

from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType
from typing import Optional, Self

import httpx

from port_ocean.rate_limiting.models import CentralizedRateLimitState
from port_ocean.rate_limiting.utils import (
    await_centralized_rate_limit,
    record_centralized_rate_limit,
    use_centralized_rate_limiting,
)


class RateLimitWrapper(ABC):
    """Integration subclass; routes centralized vs local per call site."""

    def __init__(self, pool: str) -> None:
        self.pool = pool

    async def __aenter__(self) -> Self:
        if use_centralized_rate_limiting():
            return self
        await self._local_acquire()
        return self

    async def acquire(self) -> None:
        """RetryTransport: wait for admission before each outbound attempt."""
        if use_centralized_rate_limiting():
            await await_centralized_rate_limit(self.pool)

    async def record_rate_limit_response(
        self, response: httpx.Response, *, context: str = "transport-retry"
    ) -> None:
        if use_centralized_rate_limiting():
            state = self._parse_centralized_state(response, context)
            if state is not None:
                await record_centralized_rate_limit(
                    self.pool,
                    state,
                    is_rate_limited=self._centralized_is_rate_limited(response),
                )
            return
        if context == "transport-retry":
            return
        await self._local_ingest_response(response, context)

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        if not use_centralized_rate_limiting():
            await self._local_release(exc_type, exc_val, exc_tb)

    def is_close_to_rate_limit(self) -> bool:
        if use_centralized_rate_limiting():
            return False
        return self._local_is_close_to_rate_limit()

    def seconds_until_rate_limit_reset(self) -> float:
        if use_centralized_rate_limiting():
            return 0.0
        return self._local_seconds_until_rate_limit_reset()

    async def notify_transport_rate_limit_retry(self, response: httpx.Response) -> None:
        """Local-only: GitHubRetryTransport lock before retry sleep on rate-limit responses."""
        if use_centralized_rate_limiting():
            return
        await self._notify_transport_rate_limit_retry(response)

    @abstractmethod
    async def _local_acquire(self) -> None: ...

    @abstractmethod
    async def _notify_transport_rate_limit_retry(
        self, response: httpx.Response
    ) -> None: ...

    @abstractmethod
    async def _local_release(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None: ...

    @abstractmethod
    async def _local_ingest_response(
        self, response: httpx.Response, context: str
    ) -> None: ...

    @abstractmethod
    def _parse_centralized_state(
        self, response: httpx.Response, context: str
    ) -> Optional[CentralizedRateLimitState]: ...

    @abstractmethod
    def _centralized_is_rate_limited(self, response: httpx.Response) -> bool: ...

    @abstractmethod
    def _local_is_close_to_rate_limit(self) -> bool: ...

    @abstractmethod
    def _local_seconds_until_rate_limit_reset(self) -> float: ...
