import asyncio
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator

import httpx
from loguru import logger

API_PREFIX = "/api/v2/"
MAX_CONCURRENT_REQUESTS = 10
# Headroom for the requests already in flight when the budget is read.
PAUSE_AT_REMAINING = 3
# The only ids this integration sends. Organization segments are names, not ids.
RESOURCE_ID_PREFIXES = ("ws-", "run-", "sv-")


@dataclass
class RateLimitInfo:
    limit: int
    remaining: int
    reset_at: float

    @property
    def seconds_until_reset(self) -> float:
        return max(0.0, self.reset_at - time.monotonic())


def budget_key(url: httpx.URL) -> str:
    """Terraform counts a budget per endpoint, not per resource, so resource ids
    collapse and every workspace's runs share one key."""
    if not url.path.startswith(API_PREFIX):
        # Archivist paths are unique per object; one key keeps the lock map bounded.
        return "non-api"

    segments = url.path.removeprefix(API_PREFIX).strip("/").split("/")
    return "/".join(
        "*" if segment.startswith(RESOURCE_ID_PREFIXES) else segment
        for segment in segments
    )


class TerraformRateLimiter:
    """Paces requests from HCP Terraform's own rate limit headers.

    The budget is 30 requests per window, and x-ratelimit-reset puts that window at
    roughly 14 seconds. A per-second limiter cannot express that: the 25 per second this
    replaces spends a whole window in just over a second.

    One budget covers an endpoint shape rather than an individual resource, so budget_key
    collapses resource ids. Draining one workspace's runs also returns 429 on a second
    workspace's runs, while account/details is unaffected.
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
                if info and info.remaining <= PAUSE_AT_REMAINING:
                    sleep_for = info.seconds_until_reset
                    if sleep_for > 0:
                        logger.warning(
                            f"Rate limit budget for {key} spent "
                            f"({info.remaining}/{info.limit}), pausing {sleep_for:.2f}s"
                        )
                        await asyncio.sleep(sleep_for)
                        # A response may have refreshed the budget while we paused.
                        info = self._budgets.get(key)
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

        known = self._budgets.get(key)
        if known and known.seconds_until_reset > 0:
            # While the window is live the count only falls: a response that left the
            # server before the drain cannot refill it.
            info.remaining = min(known.remaining, info.remaining)

        self._budgets[key] = info
        logger.debug(
            f"Rate limit for {key}: {info.remaining}/{info.limit} remaining, "
            f"resets in {info.seconds_until_reset:.2f}s"
        )
