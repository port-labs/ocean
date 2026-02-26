import asyncio
import time
from typing import Optional, Any, Type

import httpx
from loguru import logger
from github.clients.rate_limiter.utils import (
    GitHubRateLimiterConfig,
    RateLimitInfo,
    RateLimiterRequiredHeaders,
    is_rate_limit_response,
)


class GitHubRateLimiter:
    def __init__(self, config: GitHubRateLimiterConfig) -> None:
        self.api_type = config.api_type
        self._semaphore = asyncio.Semaphore(config.max_concurrent)
        self.rate_limit_info: Optional[RateLimitInfo] = None
        self._lock = asyncio.Lock()
        self._initialized: bool = False

    async def __aenter__(self) -> "GitHubRateLimiter":
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

    async def _enforce_rate_limit(self) -> None:
        if not self._initialized or self.rate_limit_info is None:
            return

        if int(time.time()) >= self.rate_limit_info.reset_time:
            self._initialized = False
            return

        if self.rate_limit_info.remaining <= 1:
            delay = self.rate_limit_info.seconds_until_reset
            if delay > 0:
                logger.bind(api_type=self.api_type, delay=delay).warning(
                    f"Requests paused for {delay:.1f}s due to rate limit"
                )
                await asyncio.sleep(delay)
            self._initialized = False
            return

        self.rate_limit_info.remaining -= 1

    def is_rate_limit_response(self, response: httpx.Response) -> bool:
        return is_rate_limit_response(response)

    def _parse_rate_limit_headers(
        self, headers: RateLimiterRequiredHeaders
    ) -> Optional[RateLimitInfo]:
        if not (
            headers.x_ratelimit_limit
            and headers.x_ratelimit_remaining
            and headers.x_ratelimit_reset
        ):
            return None

        return RateLimitInfo(
            limit=int(headers.x_ratelimit_limit),
            remaining=int(headers.x_ratelimit_remaining),
            reset_time=int(headers.x_ratelimit_reset),
        )

    def _parse_retry_after(self, headers: RateLimiterRequiredHeaders) -> Optional[int]:
        if headers.retry_after is None:
            return None
        try:
            return int(headers.retry_after)
        except ValueError:
            return None

    async def notify_rate_limited(self, response: httpx.Response) -> None:
        headers = RateLimiterRequiredHeaders(**response.headers)
        async with self._lock:
            self._handle_rate_limit_response(headers, "transport-retry")

    async def on_response(self, response: httpx.Response, resource: str) -> None:
        rate_limit_headers = RateLimiterRequiredHeaders(**response.headers)

        async with self._lock:
            if self.is_rate_limit_response(response):
                self._handle_rate_limit_response(rate_limit_headers, resource)
                return

            epoch_passed = (
                self.rate_limit_info is not None
                and int(time.time()) >= self.rate_limit_info.reset_time
            )
            stale_exhausted = (
                self.rate_limit_info is not None and self.rate_limit_info.remaining <= 0
            )
            if not self._initialized or epoch_passed or stale_exhausted:
                self._initialize_from_response(rate_limit_headers, resource)

    def _handle_rate_limit_response(
        self, headers: RateLimiterRequiredHeaders, resource: str
    ) -> None:
        info = self._parse_rate_limit_headers(headers)
        retry_after_seconds = self._parse_retry_after(headers)

        if info is None and retry_after_seconds is not None:
            info = RateLimitInfo(
                limit=self.rate_limit_info.limit if self.rate_limit_info else 0,
                remaining=0,
                reset_time=int(time.time()) + retry_after_seconds,
            )
        elif info is not None:
            if retry_after_seconds is not None:
                info.reset_time = int(time.time()) + retry_after_seconds
            info.remaining = 0

        if info is None:
            return

        existing_reset = self.rate_limit_info.reset_time if self.rate_limit_info else 0
        if info.reset_time <= max(int(time.time()), existing_reset):
            return

        self.rate_limit_info = info
        self._initialized = True
        logger.bind(
            api_type=self.api_type,
            resource=resource,
            resets_in=info.seconds_until_reset,
        ).warning(
            f"GitHub rate limit exhausted for {self.api_type} on {resource}: "
            f"resets in {info.seconds_until_reset}s"
        )

    def _initialize_from_response(
        self, headers: RateLimiterRequiredHeaders, resource: str
    ) -> None:
        info = self._parse_rate_limit_headers(headers)
        if info is None:
            return

        self.rate_limit_info = info
        self._initialized = True
        self._log_rate_limit_status(info, resource)

    def _log_rate_limit_status(self, info: RateLimitInfo, resource: str) -> None:
        resets_in = info.seconds_until_reset
        bound = logger.bind(
            api_type=self.api_type,
            resource=resource,
            remaining=info.remaining,
            limit=info.limit,
            resets_in=resets_in,
        )
        base_message = (
            f"GitHub rate limit for {self.api_type} on {resource}: "
            f"{info.remaining}/{info.limit} remaining (resets in {resets_in}s)"
        )

        if info.remaining <= 0:
            bound.warning(f"Exhausted — {base_message}")
        elif info.remaining <= info.limit * 0.1:
            bound.warning(f"Near exhaustion — {base_message}")
        else:
            bound.debug(f"Status — {base_message}")
