from typing import Any, AsyncGenerator
import asyncio
from port_ocean.utils.async_iterators import semaphore_async_iterator
import pytest


@pytest.mark.asyncio
async def test_semaphore_async_iterator() -> None:
    max_concurrency = 5
    semaphore = asyncio.BoundedSemaphore(max_concurrency)

    concurrent_tasks = 0
    max_concurrent_tasks = 0
    lock = asyncio.Lock()  # Protect shared variables

    num_tasks = 20

    async def mock_function() -> AsyncGenerator[str, None]:
        nonlocal concurrent_tasks, max_concurrent_tasks

        async with lock:
            concurrent_tasks += 1
            if concurrent_tasks > max_concurrent_tasks:
                max_concurrent_tasks = concurrent_tasks

        await asyncio.sleep(0.1)
        yield "result"

        async with lock:
            concurrent_tasks -= 1

    async def consume_iterator(async_iterator: Any) -> None:
        async for _ in async_iterator:
            pass

    tasks = [
        consume_iterator(semaphore_async_iterator(semaphore, mock_function))
        for _ in range(num_tasks)
    ]
    await asyncio.gather(*tasks)

    assert (
        max_concurrent_tasks <= max_concurrency
    ), f"Max concurrent tasks {max_concurrent_tasks} exceeded semaphore limit {max_concurrency}"
    assert concurrent_tasks == 0, "Not all tasks have completed"
