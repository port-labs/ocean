import time
import asyncio
from typing import List, Optional, Dict, Any, Type
import httpx
from loguru import logger
from github.clients.rate_limiter.utils import (
    GitHubRateLimiterConfig,
    PauseUntil,
    RateLimitInfo,
    RateLimiterRequiredHeaders,
)


class GitHubRateLimiter:
    def __init__(self, config: GitHubRateLimiterConfig) -> None:
        self.api_type = config.api_type
        self.max_retries = config.max_retries
        self._semaphore = asyncio.Semaphore(config.max_concurrent)
        self._rate_limit_info: Optional[RateLimitInfo] = None

        self._pause = PauseUntil()
        self._block_lock = asyncio.Lock()
        self._current_resource: Optional[str] = None

    async def __aenter__(self) -> "GitHubRateLimiter":
        await self._semaphore.acquire()

        async with self._block_lock:
            if self._pause.is_active():
                delay = self._pause.seconds_remaining()
                if delay > 0:
                    logger.warning(
                        f"{self.api_type} requests paused for {delay:.1f}s due to earlier rate limit"
                    )
                    await asyncio.sleep(delay)
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> Optional[bool]:
        try:
            if exc_type is not None and exc_val is not None:
                if isinstance(exc_val, httpx.HTTPStatusError):
                    backoff_time = self._handle_rate_limit_error(exc_val.response)
                    if backoff_time:
                        logger.warning(
                            f"Rate limit hit for {self.api_type}, waiting {backoff_time:.1f} seconds"
                        )
                        await asyncio.sleep(backoff_time)
                        return True
        finally:
            self._semaphore.release()

        return None

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

    def _get_backoff_time(self, response: httpx.Response) -> Optional[float]:
        buffer = 5.0  # Add 5 seconds to whatever GitHub says

        retry_after = response.headers.get("Retry-After")
        if retry_after:
            return float(retry_after) + buffer

        reset_time = response.headers.get("X-RateLimit-Reset")
        if reset_time:
            return float(reset_time) - time.time() + buffer

        return None

    def get_rate_limit_status_codes(self) -> List[int]:
        return [403, 429]

    def _handle_rate_limit_error(self, response: httpx.Response) -> Optional[float]:
        if response.status_code in self.get_rate_limit_status_codes():
            backoff_time = self._get_backoff_time(response)
            if backoff_time:
                self._pause.set(backoff_time)
                logger.warning(
                    f"{self.api_type} rate limit hit. "
                    f"Pausing all {self.api_type} requests for {backoff_time:.1f}s"
                )
                return backoff_time
        return None

    def is_rate_limit_response(self, response: httpx.Response) -> bool:
        status_code = response.status_code
        headers = response.headers

        if status_code not in self.get_rate_limit_status_codes():
            return False

        return status_code == 429 or (
            headers.get("X-RateLimit-Remaining") == "0"
            and headers.get("X-RateLimit-Reset") is not None
        )

    def update_rate_limits(
        self, headers: httpx.Headers, resource: str
    ) -> Optional[RateLimitInfo]:

        rate_limit_headers = RateLimiterRequiredHeaders(**headers)

        info = self._parse_rate_limit_headers(rate_limit_headers)
        if info:
            self._rate_limit_info = info
            logger.debug(
                f"Rate limit hit on {resource} for {self.api_type}: {info.remaining}/{info.limit} remaining"
            )
        return info

    def get_rate_limit_status(self) -> Dict[str, Any]:
        if not self._rate_limit_info:
            return {}

        info = self._rate_limit_info
        return {
            self.api_type: {
                "limit": info.limit,
                "remaining": info.remaining,
                "reset_time": info.reset_time,
                "seconds_until_reset": info.seconds_until_reset,
                "utilization_percentage": ((info.limit - info.remaining) / info.limit)
                * 100,
            }
        }

    def log_rate_limit_status(self) -> None:
        status = self.get_rate_limit_status()
        if not status:
            return

        info = status[self.api_type]
        logger.debug(
            f"{self.api_type}: {info['remaining']}/{info['limit']} remaining "
            f"({info['utilization_percentage']:.1f}% used) - "
            f"resets in {info['seconds_until_reset']}s"
        )

    def is_paused(self) -> bool:
        return self._pause.is_active()
