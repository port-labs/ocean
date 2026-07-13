import asyncio
import time

import pytest

from wiz.rate_limiter import TokenBucketRateLimiter


@pytest.mark.asyncio
async def test_token_bucket_limits_burst() -> None:
    limiter = TokenBucketRateLimiter(rate=10, burst=10)
    start = time.monotonic()

    for _ in range(10):
        await limiter.acquire()

    elapsed = time.monotonic() - start
    assert elapsed < 0.1


@pytest.mark.asyncio
async def test_token_bucket_paces_sustained_requests() -> None:
    limiter = TokenBucketRateLimiter(rate=10, burst=1)
    start = time.monotonic()

    for _ in range(3):
        await limiter.acquire()

    elapsed = time.monotonic() - start
    assert elapsed >= 0.15


@pytest.mark.asyncio
async def test_token_bucket_serializes_concurrent_acquires() -> None:
    limiter = TokenBucketRateLimiter(rate=5, burst=1)
    start = time.monotonic()

    await asyncio.gather(*(limiter.acquire() for _ in range(3)))

    elapsed = time.monotonic() - start
    assert elapsed >= 0.3


def test_set_rate_updates_burst_by_default() -> None:
    limiter = TokenBucketRateLimiter(rate=10, burst=10)
    limiter.set_rate(5)

    assert limiter.rate == 5
