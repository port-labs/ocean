import asyncio
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

        self._block_lock = asyncio.Lock()
        self._current_resource: Optional[str] = None

    async def __aenter__(self) -> "GitHubRateLimiter":
        await self._semaphore.acquire()

        async with self._block_lock:
            if self.rate_limit_info and (self.rate_limit_info.remaining <= 1):
                delay = self.rate_limit_info.seconds_until_reset
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

        return status_code == 429 or has_exhausted_rate_limit_headers(headers)

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
        if not info:
            return None

        self.rate_limit_info = info
        self._log_rate_limit_status(info, resource)
        return info

    def _log_rate_limit_status(self, info: RateLimitInfo, resource: str) -> None:
        resets_in = info.seconds_until_reset
        message = (
            f"GitHub rate limit status on {resource} for {self.api_type}: "
            f"{info.remaining}/{info.limit} remaining (resets in {resets_in}s)"
        )

        if info.remaining <= 0:
            logger.warning(message.replace("status", "exhausted"))
        elif info.remaining <= 1:
            logger.warning(message.replace("status", "near exhaustion"))
        else:
            logger.debug(message)
