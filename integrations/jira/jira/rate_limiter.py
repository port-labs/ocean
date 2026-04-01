import asyncio
import time
from dataclasses import dataclass
from typing import Optional, Any, Type
from datetime import datetime

import httpx
from loguru import logger


MAX_CONCURRENT_REQUESTS = 10
MINIMUM_LIMIT_REMAINING = 1
RATE_LIMIT_STATUS_CODE = 429
DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 1


@dataclass
class JiraRateLimitInfo:
    """Tracks the current state of Jira's rate limit window."""

    limit: int
    remaining: int
    reset_time: float

    @property
    def seconds_until_reset(self) -> float:
        return max(0.0, self.reset_time - time.time())

    @property
    def is_expired(self) -> bool:
        return time.time() >= self.reset_time


def is_rate_limit_response(response: httpx.Response) -> bool:
    return response.status_code == RATE_LIMIT_STATUS_CODE


class JiraRateLimiter:
    """
    Asynchronous rate limiter for Atlassian Jira Cloud APIs.

    Conforms to Ocean's async standards by supporting concurrent control,
    proactive throttling, and reactive backoff using Jira rate limit headers.
    """

    def __init__(
        self,
        max_concurrent: int = MAX_CONCURRENT_REQUESTS,
        minimum_limit_remaining: int = MINIMUM_LIMIT_REMAINING,
    ) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._lock = asyncio.Lock()

        self._rate_limit_info: Optional[JiraRateLimitInfo] = None
        self._near_limit: bool = False
        self._retry_after: Optional[float] = None
        self._initialized: bool = False

        self._minimum_limit_remaining = minimum_limit_remaining

    @property
    def seconds_until_reset(self) -> float:
        """Time in seconds until the current rate limit window resets."""
        if self._rate_limit_info:
            return self._rate_limit_info.seconds_until_reset
        return 0.0

    def _reset_window(self) -> None:
        """Reset transient flags after a rate limit window has passed.

        Preserves _initialized and _rate_limit_info.limit so the limiter
        retains knowledge of the server's rate limit even when normal (200)
        responses omit the x-ratelimit-reset header.
        """
        self._near_limit = False
        self._retry_after = None
        if self._rate_limit_info is not None:
            self._rate_limit_info.remaining = self._rate_limit_info.limit

    async def _enforce_rate_limit(self) -> None:
        """Proactively sleep if rate limit is near exhaustion or retry-after is active."""
        if not self._initialized or self._rate_limit_info is None:
            return

        if self._rate_limit_info.is_expired:
            self._reset_window()
            return

        if self._retry_after is not None and self._retry_after > 0:
            delay = self._retry_after
            logger.bind(delay=delay).warning(
                f"Requests paused for {delay:.1f}s due to retry-after header"
            )
            await asyncio.sleep(delay)
            self._retry_after = None
            return

        remaining_condition = (
            self._rate_limit_info.remaining <= self._minimum_limit_remaining
        )

        if self._near_limit or remaining_condition:
            delay = self._rate_limit_info.seconds_until_reset
            if delay > 0:
                logger.bind(
                    remaining=self._rate_limit_info.remaining,
                    limit=self._rate_limit_info.limit,
                    resets_in=delay,
                    near_limit=self._near_limit,
                ).warning(f"Requests paused for {delay:.1f}s due to rate limit")
                await asyncio.sleep(delay)
            self._reset_window()
            return

        self._rate_limit_info.remaining -= 1

    def is_rate_limit_response(self, response: httpx.Response) -> bool:
        return is_rate_limit_response(response)

    async def on_response(self, response: httpx.Response) -> None:
        """
        Process response headers to update rate limit state. Should be called
        by the client after every request, including failed ones.
        """
        async with self._lock:
            if self.is_rate_limit_response(response):
                self._handle_rate_limit_response(response.headers)
                return

            epoch_passed = (
                self._rate_limit_info is not None and self._rate_limit_info.is_expired
            )
            stale_exhausted = (
                self._rate_limit_info is not None
                and self._rate_limit_info.remaining <= 0
            )
            if not self._initialized or epoch_passed or stale_exhausted:
                self._initialize_from_response(response.headers)
            elif self._rate_limit_info is not None:
                server_remaining = response.headers.get("x-ratelimit-remaining")
                if server_remaining is not None:
                    try:
                        sr = int(server_remaining)
                        if sr > self._rate_limit_info.remaining:
                            self._rate_limit_info.remaining = sr
                    except (ValueError, TypeError):
                        pass

    def _parse_retry_after(self, headers: httpx.Headers) -> Optional[float]:
        retry_after_value = headers.get("retry-after")
        if retry_after_value is None:
            return None
        try:
            return float(retry_after_value)
        except (ValueError, TypeError):
            return None

    def _handle_rate_limit_response(self, headers: httpx.Headers) -> None:
        """Handle a 429 rate-limited response by updating state."""
        info = self._parse_partial_rate_limit_headers(headers)
        retry_after_seconds = self._parse_retry_after(headers)

        self._near_limit = headers.get("x-ratelimit-nearlimit") == "true"

        reason = headers.get("ratelimit-reason")

        # Build rate limit info from retry-after if headers are missing
        if info is None and retry_after_seconds is not None:
            info = JiraRateLimitInfo(
                limit=self._rate_limit_info.limit if self._rate_limit_info else 0,
                remaining=0,
                reset_time=time.time() + retry_after_seconds,
            )
        elif info is not None:
            if retry_after_seconds is not None:
                info.reset_time = time.time() + retry_after_seconds
            info.remaining = 0

        if info is None:
            return

        # Don't regress to an older reset time
        existing_reset = (
            self._rate_limit_info.reset_time if self._rate_limit_info else 0
        )
        if info.reset_time <= max(time.time(), existing_reset):
            return

        self._rate_limit_info = info
        self._retry_after = retry_after_seconds
        self._initialized = True

        logger.bind(
            remaining=info.remaining,
            limit=info.limit,
            resets_in=info.seconds_until_reset,
            reason=reason,
        ).warning(
            f"Jira rate limit exhausted: "
            f"resets in {info.seconds_until_reset:.0f}s"
            f"{f' (reason: {reason})' if reason else ''}"
        )

    def _parse_partial_rate_limit_headers(
        self, headers: httpx.Headers
    ) -> Optional[JiraRateLimitInfo]:
        """Parse rate limit headers when x-ratelimit-reset may be absent.

        Normal (non-429) Jira responses include x-ratelimit-limit and
        x-ratelimit-remaining but omit x-ratelimit-reset.  When reset is
        missing we synthesise a window using DEFAULT_RATE_LIMIT_WINDOW_SECONDS
        so that the limiter can still track remaining quota proactively.
        """
        limit_value = headers.get("x-ratelimit-limit")
        remaining_value = headers.get("x-ratelimit-remaining")
        reset_time_str = headers.get("x-ratelimit-reset")

        if not (limit_value and remaining_value):
            return None

        try:
            limit = int(limit_value)
            remaining = int(remaining_value)
        except (ValueError, TypeError):
            return None

        if reset_time_str:
            try:
                dt = datetime.fromisoformat(reset_time_str.replace("Z", "+00:00"))
                reset_time = dt.timestamp()
            except (ValueError, TypeError):
                reset_time = time.time() + DEFAULT_RATE_LIMIT_WINDOW_SECONDS
        else:
            reset_time = time.time() + DEFAULT_RATE_LIMIT_WINDOW_SECONDS

        return JiraRateLimitInfo(
            limit=limit,
            remaining=remaining,
            reset_time=reset_time,
        )

    def _initialize_from_response(self, headers: httpx.Headers) -> None:
        """Initialize rate limit tracking from a normal (non-429) response.

        Jira normal responses typically include x-ratelimit-limit and
        x-ratelimit-remaining but omit x-ratelimit-reset.  We accept
        partial headers so the limiter can activate proactively.
        """
        info = self._parse_partial_rate_limit_headers(headers)
        if info is None:
            return

        self._near_limit = headers.get("x-ratelimit-nearlimit") == "true"
        self._rate_limit_info = info
        self._initialized = True

        retry_after_value = headers.get("retry-after")
        if retry_after_value is not None:
            try:
                self._retry_after = float(retry_after_value)
            except (ValueError, TypeError):
                pass

        self._log_rate_limit_status(info)

    def _log_rate_limit_status(self, info: JiraRateLimitInfo) -> None:
        resets_in = info.seconds_until_reset
        bound = logger.bind(
            remaining=info.remaining,
            limit=info.limit,
            resets_in=resets_in,
        )
        base_message = (
            f"Jira rate limit: "
            f"{info.remaining}/{info.limit} remaining (resets in {resets_in:.0f}s)"
        )

        if info.remaining <= 0:
            bound.warning(f"Exhausted — {base_message}")
        elif info.remaining <= info.limit * 0.1:
            bound.warning(f"Near exhaustion — {base_message}")
        else:
            bound.debug(f"Status — {base_message}")

    async def __aenter__(self) -> "JiraRateLimiter":
        """Acquires semaphore and proactively sleeps if the rate limit is low."""
        await self._semaphore.acquire()

        async with self._lock:
            await self._enforce_rate_limit()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        self._semaphore.release()
