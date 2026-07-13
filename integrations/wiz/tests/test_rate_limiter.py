import asyncio
import time

import pytest

from wiz.rate_limiter import TokenBucketRateLimiter


@pytest.mark.asyncio
async def test_token_bucket_allows_initial_burst() -> None:
    limiter = TokenBucketRateLimiter(rate=10)
    start = time.monotonic()

    for _ in range(10):
        await limiter.acquire()

    elapsed = time.monotonic() - start
    assert elapsed < 0.1


@pytest.mark.asyncio
async def test_token_bucket_paces_sustained_requests() -> None:
    limiter = TokenBucketRateLimiter(rate=10)
    start = time.monotonic()

    for _ in range(12):
        await limiter.acquire()

    elapsed = time.monotonic() - start
    assert elapsed >= 0.15


@pytest.mark.asyncio
async def test_token_bucket_serializes_concurrent_acquires() -> None:
    limiter = TokenBucketRateLimiter(rate=5)
    start = time.monotonic()

    await asyncio.gather(*(limiter.acquire() for _ in range(6)))

    elapsed = time.monotonic() - start
    assert elapsed >= 0.15
