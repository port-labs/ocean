import asyncio
from loguru import logger
import httpx
from typing import Callable, Any


class RateLimiter:
    def __init__(self, max_retries: int = 3, safe_minimum: int = 10):
        self.max_retries = max_retries
        self.safe_minimum = safe_minimum

    async def call_with_rate_limiting(self, func: Callable, *args, **kwargs) -> Any:
        retry_count = 0
        while retry_count < self.max_retries:
            try:
                return await func(*args, **kwargs)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    await self.handle_rate_limiting(e.response)
                    retry_count += 1
                    continue
                else:
                    logger.error(
                        f"Client error {e.response.status_code} for URL: {e.request.url} - {e.response.text}"
                    )
                    return {}

    async def handle_rate_limiting(self, response: httpx.Response) -> None:
        requests_remaining = int(response.headers.get("ratelimit-remaining", 0))
        reset_time = int(response.headers.get("ratelimit-reset", 0))
        logger.info(
            f"Remaining {requests_remaining} requests, reset time {reset_time} seconds"
        )
        logger.warning(
            f"Low request limit. Waiting for {reset_time} seconds before next call."
        )
        await asyncio.sleep(reset_time)
