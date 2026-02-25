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
        logger.info(
            f"[RateLimiter:{self.api_type}] acquiring semaphore "
            f"(available={self._semaphore._value})"
        )
        await self._semaphore.acquire()
        logger.info(
            f"[RateLimiter:{self.api_type}] semaphore acquired "
            f"(available={self._semaphore._value})"
        )

        async with self._block_lock:
            if self.rate_limit_info and (self.rate_limit_info.remaining <= 1):
                delay = self.rate_limit_info.seconds_until_reset
                if delay > 0:
                    logger.warning(
                        f"[RateLimiter:{self.api_type}] proactive pause — "
                        f"remaining={self.rate_limit_info.remaining}/{self.rate_limit_info.limit}, "
                        f"sleeping {delay:.1f}s until rate limit resets"
                    )
                    await asyncio.sleep(delay)
                    logger.info(
                        f"[RateLimiter:{self.api_type}] resumed after {delay:.1f}s pause"
                    )
                else:
                    logger.info(
                        f"[RateLimiter:{self.api_type}] rate limit nearly exhausted "
                        f"(remaining={self.rate_limit_info.remaining}) but reset is in the past, proceeding"
                    )
            else:
                remaining = self.rate_limit_info.remaining if self.rate_limit_info else "unknown"
                limit = self.rate_limit_info.limit if self.rate_limit_info else "unknown"
                logger.info(
                    f"[RateLimiter:{self.api_type}] no pause needed — "
                    f"remaining={remaining}/{limit}"
                )
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        self._semaphore.release()
        if exc_type is not None:
            logger.info(
                f"[RateLimiter:{self.api_type}] released semaphore with exception: "
                f"{exc_type.__name__}"
            )

    def get_rate_limit_status_codes(self) -> List[int]:
        return [403, 429]

    def is_rate_limit_response(self, response: httpx.Response) -> bool:
        status_code = response.status_code
        headers = response.headers

        if status_code not in self.get_rate_limit_status_codes():
            return False

        is_rate_limit = status_code == 429 or has_exhausted_rate_limit_headers(headers)
        logger.info(
            f"[RateLimiter:{self.api_type}] is_rate_limit_response check — "
            f"status={status_code}, result={is_rate_limit}, "
            f"x-ratelimit-remaining={headers.get('x-ratelimit-remaining', '?')}"
        )
        return is_rate_limit

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
            logger.info(
                f"[RateLimiter:{self.api_type}] no rate limit headers found in response for {resource}"
            )
            return None

        prev = self.rate_limit_info
        self.rate_limit_info = info
        if prev and prev.remaining != info.remaining:
            logger.info(
                f"[RateLimiter:{self.api_type}] rate limit updated for {resource}: "
                f"{prev.remaining} -> {info.remaining}/{info.limit} "
                f"(reset in {info.seconds_until_reset:.0f}s)"
            )
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
            logger.info(message)
