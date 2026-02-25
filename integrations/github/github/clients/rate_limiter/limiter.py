import asyncio
import time
from typing import List, Optional, Any, Type
import httpx
from loguru import logger
from github.clients.rate_limiter.utils import (
    GitHubRateLimiterConfig,
    RateLimitInfo,
    RateLimiterRequiredHeaders,
)
from github.helpers.utils import has_exhausted_rate_limit_headers


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
                logger.warning(
                    f"{self.api_type} requests paused for {delay:.1f}s due to rate limit"
                )
                await asyncio.sleep(delay)
            self._initialized = False
            return

        self.rate_limit_info.remaining -= 1

    def get_rate_limit_status_codes(self) -> List[int]:
        return [403, 429]

    def is_rate_limit_response(self, response: httpx.Response) -> bool:
        if response.status_code not in self.get_rate_limit_status_codes():
            return False
        return response.status_code == 429 or has_exhausted_rate_limit_headers(
            response.headers
        )

    def on_response(self, response: httpx.Response, resource: str) -> None:
        if self.is_rate_limit_response(response):
            self._handle_rate_limit_response(response, resource)
            return

        if not self._initialized:
            self._initialize_from_response(response, resource)

    def _handle_rate_limit_response(
        self, response: httpx.Response, resource: str
    ) -> None:
        headers = RateLimiterRequiredHeaders(**response.headers)
        info = self._parse_rate_limit_headers(headers)
        retry_after = self._parse_retry_after(headers)

        if info is None and retry_after is not None:
            info = RateLimitInfo(
                limit=self.rate_limit_info.limit if self.rate_limit_info else 0,
                remaining=0,
                reset_time=int(time.time()) + retry_after,
            )
        elif info is not None:
            info.remaining = 0
            if retry_after is not None:
                info.reset_time = int(time.time()) + retry_after

        if info is not None:
            self.rate_limit_info = info
            self._initialized = True
            logger.warning(
                f"GitHub rate limit exhausted for {self.api_type} on {resource}: "
                f"resets in {info.seconds_until_reset}s"
            )

    def _initialize_from_response(
        self, response: httpx.Response, resource: str
    ) -> None:
        headers = RateLimiterRequiredHeaders(**response.headers)
        info = self._parse_rate_limit_headers(headers)
        if info is None:
            return
        self.rate_limit_info = info
        self._initialized = True
        self._log_rate_limit_status(info, resource)

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

    def _log_rate_limit_status(self, info: RateLimitInfo, resource: str) -> None:
        base = (
            f"GitHub rate limit for {self.api_type} on {resource}: "
            f"{info.remaining}/{info.limit} remaining "
            f"(resets in {info.seconds_until_reset}s)"
        )

        if info.remaining <= 0:
            logger.warning(f"Exhausted — {base}")
        elif info.remaining <= info.limit * 0.1:
            logger.warning(f"Near exhaustion — {base}")
        else:
            logger.debug(f"Initialized — {base}")
