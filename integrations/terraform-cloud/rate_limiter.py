import asyncio
import re
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator

import httpx
from loguru import logger

MAX_CONCURRENT_REQUESTS = 10
# Pause once the window is nearly spent rather than at zero, so in-flight requests do
# not tip it over while the budget is being read.
PAUSE_AT_UTILIZATION = 90.0
# Resource ids look like ws-b6PJa69T989mRSNy; resource names like state-versions do not.
RESOURCE_ID = re.compile(r"^[a-z]{2,4}-[A-Za-z0-9]{8,}$")


@dataclass
class RateLimitInfo:
    limit: int
    remaining: int
    reset_at: float

    @property
    def seconds_until_reset(self) -> float:
        return max(0.0, self.reset_at - time.monotonic())

    @property
    def utilization_percentage(self) -> float:
        if self.limit <= 0:
            return 0.0
        used = self.limit - self.remaining
        return max(0.0, min(100.0, (used / self.limit) * 100.0))


def budget_key(url: httpx.URL) -> str:
    """Collapse resource ids so every workspace's runs share one budget."""
    segments = url.path.removeprefix("/api/v2/").strip("/").split("/")
    return "/".join(
        "*" if RESOURCE_ID.match(segment) else segment for segment in segments
    )


class TerraformRateLimiter:
    """Paces requests from HCP Terraform's own rate limit headers.

    A fixed requests-per-second limiter cannot stay inside this API's budget: the limit
    is 30 requests, but x-ratelimit-reset reports a window of roughly 14 seconds rather
    than 1, and each resource carries its own budget. Measured on Ocean-Test
    2026-10-21: 120 serial requests to one workspace's runs drained
    x-ratelimit-remaining from 27 to 0 in 12s, then returned 429 until the window reset.
    """

    def __init__(self, max_concurrent: int = MAX_CONCURRENT_REQUESTS) -> None:
        self._semaphore = asyncio.BoundedSemaphore(max_concurrent)
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._budgets: dict[str, RateLimitInfo] = {}

    @asynccontextmanager
    async def budget(self, key: str) -> AsyncIterator[None]:
        await self._semaphore.acquire()
        try:
            # Held across the sleep on purpose: one waiter pauses, the rest queue behind
            # it instead of each sleeping for a window that has already passed. One lock
            # per key, so a spent resource does not stall another resource's waiters.
            async with self._locks[key]:
                info = self._budgets.get(key)
                if info and info.utilization_percentage >= PAUSE_AT_UTILIZATION:
                    sleep_for = info.seconds_until_reset
                    if sleep_for > 0:
                        logger.warning(
                            f"Rate limit budget for {key} spent "
                            f"({info.remaining}/{info.limit}), pausing {sleep_for:.2f}s"
                        )
                        await asyncio.sleep(sleep_for)
                if info:
                    # Spend it now so concurrent callers see the drain before the
                    # response arrives to correct the count.
                    info.remaining = max(0, info.remaining - 1)
            yield
        finally:
            self._semaphore.release()

    def update(self, headers: httpx.Headers, key: str) -> None:
        limit = headers.get("x-ratelimit-limit")
        remaining = headers.get("x-ratelimit-remaining")
        reset = headers.get("x-ratelimit-reset")
        if limit is None or remaining is None or reset is None:
            return

        try:
            info = RateLimitInfo(
                limit=int(limit),
                remaining=int(remaining),
                reset_at=time.monotonic() + float(reset),
            )
        except ValueError:
            logger.warning(
                f"Unparsable rate limit headers for {key}: "
                f"limit={limit} remaining={remaining} reset={reset}"
            )
            return

        self._budgets[key] = info
        logger.debug(
            f"Rate limit for {key}: {info.remaining}/{info.limit} remaining, "
            f"resets in {info.seconds_until_reset:.2f}s"
        )
