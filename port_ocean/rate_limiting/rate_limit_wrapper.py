"""Rate limit facade: local integration limiter vs cross-pod Redis.

The HTTP client holds one wrapper. ``async with`` still guards the local
semaphore. When the centralized limiter is installed, enter and exit do
nothing and ``RetryTransport`` calls ``acquire`` before each attempt.
"""

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
    """Integration subclass; each call site picks Redis or the local limiter.

    Redis on means the shared pool already waited. The local semaphore, the
    local header update, and the action-executor pause stay off so the same
    request is not delayed twice.
    """

    def __init__(self, pool: str, *, redis_enabled: bool = True) -> None:
        """``pool`` is the Redis bucket for this client, such as ``rest``.

        ``redis_enabled`` is false for a credential that must not read or write
        that bucket, such as an identity-propagated user token. The local
        limiter still applies.
        """
        self.pool = pool
        self._redis_enabled = redis_enabled

    def _redis_admission_enabled(self) -> bool:
        return self._redis_enabled and use_centralized_rate_limiting()

    async def __aenter__(self) -> Self:
        """Take the local semaphore for the ``async with`` body.

        With Redis on this is a no-op. The wait happens in ``acquire``, once
        per attempt, instead of holding a process-local slot across retries.
        """
        if self._redis_admission_enabled():
            return self
        await self._local_acquire()
        return self

    async def acquire(self) -> None:
        """Wait for cross-pod admission before this outbound attempt.

        ``RetryTransport`` calls this whenever a wrapper is configured.
        In local mode the semaphore was already taken in ``__aenter__``, so
        there is nothing left to wait for here.
        """
        if self._redis_admission_enabled():
            await await_centralized_rate_limit(self.pool)

    async def record_rate_limit_response(
        self, response: httpx.Response, *, context: str = ""
    ) -> None:
        """Publish vendor headers, or pass the response to the local limiter.

        Redis on publishes the parsed quota. A response the subclass cannot
        parse is skipped, so a header-less response does not overwrite a good
        hash with zeros. ``is_rate_limited`` comes from the subclass, usually
        a 429, and is what sets ``blocked_until``.

        Redis off forwards the response to the local limiter. That limiter
        already decides how a retry and a normal response update its state.
        """
        if self._redis_admission_enabled():
            state = self._parse_centralized_state(response, context)
            if state is not None:
                await record_centralized_rate_limit(
                    self.pool,
                    state,
                    is_rate_limited=self._centralized_is_rate_limited(response),
                )
            return
        await self._local_ingest_response(response, context)

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Release the local semaphore. Redis holds nothing for this request."""
        if not self._redis_admission_enabled():
            await self._local_release(exc_type, exc_val, exc_tb)

    def is_close_to_rate_limit(self) -> bool:
        """Whether an action executor should pause before starting more work.

        Redis admission already applied that pause, so this stays false and
        the executor does not sleep again.
        """
        if self._redis_admission_enabled():
            return False
        return self._local_is_close_to_rate_limit()

    def seconds_until_rate_limit_reset(self) -> float:
        """How long the action executor should sleep. Zero when Redis is on."""
        if self._redis_admission_enabled():
            return 0.0
        return self._local_seconds_until_rate_limit_reset()

    async def notify_transport_rate_limit_retry(self, response: httpx.Response) -> None:
        """Tell the local limiter that the transport is about to sleep on a 429.

        Redis admission covers that wait, so the local lock is not taken.
        """
        if self._redis_admission_enabled():
            return
        await self._notify_transport_rate_limit_retry(response)

    @abstractmethod
    async def _local_acquire(self) -> None:
        """Take the integration's in-process semaphore."""

    @abstractmethod
    async def _notify_transport_rate_limit_retry(
        self, response: httpx.Response
    ) -> None:
        """Record a 429 on the local limiter before the transport sleeps."""

    @abstractmethod
    async def _local_release(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Release the in-process semaphore, including when the body raised."""

    @abstractmethod
    async def _local_ingest_response(
        self, response: httpx.Response, context: str
    ) -> None:
        """Update the local limiter from a response for ``context``."""

    @abstractmethod
    def _parse_centralized_state(
        self, response: httpx.Response, context: str
    ) -> Optional[CentralizedRateLimitState]:
        """Read vendor quota headers. None when this response has none."""

    @abstractmethod
    def _centralized_is_rate_limited(self, response: httpx.Response) -> bool:
        """True when this response should set the shared ``blocked_until``."""

    @abstractmethod
    def _local_is_close_to_rate_limit(self) -> bool:
        """Local-limiter view of whether an action run should pause."""

    @abstractmethod
    def _local_seconds_until_rate_limit_reset(self) -> float:
        """Local-limiter sleep before the next action run."""
