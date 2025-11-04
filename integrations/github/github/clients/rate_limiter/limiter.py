import asyncio
from typing import List, Optional, Dict, Any, Type
import httpx
from loguru import logger
from github.clients.rate_limiter.utils import (
    GitHubRateLimiterConfig,
    RateLimitInfo,
    RateLimiterRequiredHeaders,
)


class GitHubRateLimiter:
    def __init__(self, config: GitHubRateLimiterConfig) -> None:
        self.api_type = config.api_type
        self._semaphore = asyncio.Semaphore(config.max_concurrent)
        self._rate_limit_info: Optional[RateLimitInfo] = None

        self._block_lock = asyncio.Lock()
        self._current_resource: Optional[str] = None

    async def __aenter__(self) -> "GitHubRateLimiter":
        await self._semaphore.acquire()

        async with self._block_lock:
            if self._rate_limit_info and (self._rate_limit_info.remaining <= 1):
                delay = self._rate_limit_info.seconds_until_reset
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
    ) -> None:
        self._semaphore.release()

    def get_rate_limit_status_codes(self) -> List[int]:
        return [403, 429]

    def is_rate_limit_response(self, response: httpx.Response) -> bool:
        status_code = response.status_code
        headers = response.headers

        if status_code not in self.get_rate_limit_status_codes():
            return False

        return status_code == 429 or (
            headers.get("x-ratelimit-remaining") == "0"
            and headers.get("x-ratelimit-reset") is not None
        )

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
