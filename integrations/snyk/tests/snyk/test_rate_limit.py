import pytest
import asyncio
import time
from loguru import logger
from snyk.rate_limit import RateLimiter


@pytest.mark.asyncio
async def test_concurrency_limit() -> None:
    concurrency_limit: int = 3
    requests_per_minute: int = 5
    rate_limiter: RateLimiter = RateLimiter(
        concurrency_limit=concurrency_limit, requests_per_minute=requests_per_minute
    )

    async def request_task(task_id: int) -> None:
        logger.info(f"Task {task_id} acquiring")
        await rate_limiter.acquire()
        logger.info(f"Task {task_id} acquired")
        await asyncio.sleep(0.5)  # Simulating some work
        rate_limiter.release()
        logger.info(f"Task {task_id} released")

    tasks: list[asyncio.Task] = [request_task(i) for i in range(5)]
    start_time: float = time.monotonic()
    await asyncio.gather(*tasks)
    elapsed_time: float = time.monotonic() - start_time
    assert elapsed_time >= 1.0


@pytest.mark.asyncio
async def test_rate_limit() -> None:
    rate_limiter: RateLimiter = RateLimiter(concurrency_limit=5, requests_per_minute=2)

    async def make_request() -> None:
        await rate_limiter.acquire()
        rate_limiter.release()

    start_time: float = time.monotonic()
    await asyncio.gather(make_request(), make_request(), make_request())
    elapsed_time: float = time.monotonic() - start_time
    assert elapsed_time >= 60, "Rate limiter did not properly enforce rate limit."


@pytest.mark.asyncio
async def test_request_count_reset() -> None:
    rate_limiter: RateLimiter = RateLimiter(concurrency_limit=2, requests_per_minute=2)

    await rate_limiter.acquire()
    await rate_limiter.acquire()
    rate_limiter.release()
    rate_limiter.release()

    await asyncio.sleep(60)  # Wait for the limit to reset

    start_time: float = time.monotonic()
    await rate_limiter.acquire()
    elapsed_time: float = time.monotonic() - start_time

    assert (
        elapsed_time < 1
    ), "Rate limiter did not reset request count after 60 seconds."
    rate_limiter.release()
