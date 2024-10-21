import pytest
import asyncio
import time
from loguru import logger
from snyk.rate_limit import RateLimiter  # Assuming the RateLimiter is saved in rate_limiter.py

@pytest.mark.asyncio
async def test_concurrency_limit():
    concurrency_limit = 3
    requests_per_minute = 5
    rate_limiter = RateLimiter(concurrency_limit=concurrency_limit, requests_per_minute=requests_per_minute)

    async def request_task(task_id):
        logger.info(f"Task {task_id} acquiring")
        await rate_limiter.acquire()
        logger.info(f"Task {task_id} acquired")
        await asyncio.sleep(0.5)  # Simulating some work
        rate_limiter.release()
        logger.info(f"Task {task_id} released")
    tasks = [request_task(i) for i in range(5)]
    start_time = time.monotonic()
    await asyncio.gather(*tasks)
    elapsed_time = time.monotonic() - start_time
    assert elapsed_time >= 1.0

@pytest.mark.asyncio
async def test_rate_limit():
    rate_limiter = RateLimiter(concurrency_limit=5, requests_per_minute=2)
    async def make_request():
        await rate_limiter.acquire()
        rate_limiter.release()
    start_time = time.monotonic()
    await asyncio.gather(make_request(), make_request(), make_request())
    elapsed_time = time.monotonic() - start_time
    assert elapsed_time >= 60, "Rate limiter did not properly enforce rate limit."

@pytest.mark.asyncio
async def test_request_count_reset():
    rate_limiter = RateLimiter(concurrency_limit=2, requests_per_minute=2)
    await rate_limiter.acquire()
    await rate_limiter.acquire()
    rate_limiter.release()
    rate_limiter.release()

    # Wait for the limit to reset
    await asyncio.sleep(60)

    start_time = time.monotonic()
    await rate_limiter.acquire()
    elapsed_time = time.monotonic() - start_time

    # After waiting for 60 seconds, there should be no additional delay
    assert elapsed_time < 1, "Rate limiter did not reset request count after 60 seconds."
    rate_limiter.release()
