import asyncio
from collections.abc import AsyncGenerator
from typing import Any

import pytest

from port_ocean.utils import async_iterators
from port_ocean.utils.async_iterators import (
    semaphore_async_iterator,
    stream_independent_async_iterators,
)


async def _yield_items(*items: int) -> AsyncGenerator[int, None]:
    for item in items:
        await asyncio.sleep(0)
        yield item


async def _fail_after_first() -> AsyncGenerator[int, None]:
    yield 1
    raise RuntimeError("Iterator page failed")


async def _cancel_after_first() -> AsyncGenerator[int, None]:
    yield 1
    raise asyncio.CancelledError()


async def _fail_immediately() -> AsyncGenerator[int, None]:
    should_fail = True
    if should_fail:
        raise RuntimeError("Iterator failed")
    yield 1


async def _yield_many_items() -> AsyncGenerator[int, None]:
    for item in range(100):
        yield item


async def _yield_then_fail_while_backpressured() -> AsyncGenerator[int, None]:
    yield 0
    yield 1
    raise RuntimeError("Iterator failed while backpressured")


async def _slow_to_cancel() -> AsyncGenerator[int, None]:
    yield 0
    try:
        await asyncio.sleep(3600)
    except asyncio.CancelledError:
        await asyncio.sleep(0.1)


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


async def test_stream_independent_async_iterators_streams_successful_items() -> None:
    items = [
        item
        async for item in stream_independent_async_iterators(
            _yield_items(1, 2), _yield_items(3), context="test sync"
        )
    ]

    assert sorted(items) == [1, 2, 3]


async def test_stream_independent_async_iterators_defers_failures_until_finish() -> (
    None
):
    items: list[int] = []

    with pytest.raises(ExceptionGroup) as exc_info:
        async for item in stream_independent_async_iterators(
            _fail_after_first(), _yield_items(2, 3), context="test sync"
        ):
            items.append(item)

    assert sorted(items) == [1, 2, 3]
    assert "test sync failed with 1 error(s)" in str(exc_info.value)
    assert isinstance(exc_info.value.exceptions[0], RuntimeError)


async def test_stream_independent_async_iterators_handles_independent_cancellation() -> (
    None
):
    items = [
        item
        async for item in stream_independent_async_iterators(
            _cancel_after_first(), _yield_items(2, 3), context="test sync"
        )
    ]

    assert sorted(items) == [1, 2, 3]


async def test_stream_independent_async_iterators_collects_multiple_failures() -> None:
    with pytest.raises(ExceptionGroup) as exc_info:
        async for _ in stream_independent_async_iterators(
            _fail_immediately(), _fail_after_first(), context="test sync"
        ):
            pass

    assert len(exc_info.value.exceptions) == 2


async def test_stream_independent_async_iterators_closes_while_backpressured() -> None:
    iterator = stream_independent_async_iterators(
        _yield_many_items(), context="test sync"
    )

    assert await anext(iterator) == 0
    await asyncio.wait_for(iterator.aclose(), timeout=1)


async def test_stream_independent_async_iterators_closes_while_error_is_backpressured() -> (
    None
):
    iterator = stream_independent_async_iterators(
        _yield_then_fail_while_backpressured(), context="test sync"
    )

    assert await anext(iterator) == 0
    await asyncio.sleep(0)
    await asyncio.wait_for(iterator.aclose(), timeout=1)


async def test_stream_independent_async_iterators_cleanup_wait_is_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(async_iterators, "CANCELLED_TASK_CLEANUP_TIMEOUT", 0.01)
    iterator = stream_independent_async_iterators(
        _slow_to_cancel(), context="test sync"
    )

    assert await anext(iterator) == 0
    await asyncio.wait_for(iterator.aclose(), timeout=1)
    await asyncio.sleep(0.2)
