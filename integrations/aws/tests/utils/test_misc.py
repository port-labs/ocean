from utils.misc import is_access_denied_exception
from typing import Optional, Dict, Any, AsyncGenerator
import asyncio
from utils.misc import semaphore_async_iterator
import pytest


class MockException(Exception):
    def __init__(self, response: Optional[Dict[str, Any]]) -> None:
        self.response = response


def test_access_denied_exception_with_response() -> None:
    e = MockException(response={"Error": {"Code": "AccessDenied"}})
    assert is_access_denied_exception(e)


def test_access_denied_exception_without_response() -> None:
    e = MockException(response=None)
    assert not is_access_denied_exception(e)


def test_access_denied_exception_with_other_error() -> None:
    e = MockException(response={"Error": {"Code": "SomeOtherError"}})
    assert not is_access_denied_exception(e)


def test_access_denied_exception_no_response_attribute() -> None:
    e = Exception("Test exception")
    assert not is_access_denied_exception(e)


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

    async def consume_iterator(async_iterator) -> None:
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
