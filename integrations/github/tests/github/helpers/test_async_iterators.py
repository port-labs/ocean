import asyncio
from collections.abc import AsyncGenerator, AsyncIterator

import pytest

from github.helpers import async_iterators
from github.helpers.async_iterators import stream_independent_async_iterators


async def _yield_items(*items: int) -> AsyncIterator[int]:
    for item in items:
        await asyncio.sleep(0)
        yield item


async def _fail_after_first() -> AsyncIterator[int]:
    yield 1
    raise RuntimeError("GitHub page failed")


async def _fail_immediately() -> AsyncIterator[int]:
    should_fail = True
    if should_fail:
        raise RuntimeError("GitHub repo failed")
    yield 1


async def _yield_many_items() -> AsyncIterator[int]:
    for item in range(100):
        yield item


async def _yield_then_fail_while_backpressured() -> AsyncIterator[int]:
    yield 0
    yield 1
    raise RuntimeError("GitHub page failed while backpressured")


async def _slow_to_cancel() -> AsyncIterator[int]:
    yield 0
    try:
        await asyncio.sleep(3600)
    except asyncio.CancelledError:
        await asyncio.sleep(0.1)


async def test_stream_independent_async_iterators_streams_successful_items() -> None:
    items = [
        item
        async for item in stream_independent_async_iterators(
            _yield_items(1, 2), _yield_items(3)
        )
    ]

    assert sorted(items) == [1, 2, 3]


async def test_defers_failures_until_siblings_finish() -> None:
    items: list[int] = []

    with pytest.raises(ExceptionGroup) as exc_info:
        async for item in stream_independent_async_iterators(
            _fail_after_first(), _yield_items(2, 3), context="test sync"
        ):
            items.append(item)

    assert sorted(items) == [1, 2, 3]
    assert "test sync failed with 1 error(s)" in str(exc_info.value)
    assert isinstance(exc_info.value.exceptions[0], RuntimeError)


async def test_stream_independent_async_iterators_collects_multiple_failures() -> None:
    with pytest.raises(ExceptionGroup) as exc_info:
        async for _ in stream_independent_async_iterators(
            _fail_immediately(), _fail_after_first()
        ):
            pass

    assert len(exc_info.value.exceptions) == 2


async def test_stream_independent_async_iterators_closes_while_backpressured() -> None:
    iterator: AsyncGenerator[int, None] = stream_independent_async_iterators(
        _yield_many_items()
    )

    assert await anext(iterator) == 0
    await asyncio.wait_for(iterator.aclose(), timeout=1)


async def test_stream_independent_async_iterators_closes_while_error_is_backpressured() -> (
    None
):
    iterator: AsyncGenerator[int, None] = stream_independent_async_iterators(
        _yield_then_fail_while_backpressured()
    )

    assert await anext(iterator) == 0
    await asyncio.sleep(0)
    await asyncio.wait_for(iterator.aclose(), timeout=1)


async def test_stream_independent_async_iterators_cleanup_wait_is_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(async_iterators, "CANCELLED_TASK_CLEANUP_TIMEOUT", 0.01)
    iterator: AsyncGenerator[int, None] = stream_independent_async_iterators(
        _slow_to_cancel()
    )

    assert await anext(iterator) == 0
    await asyncio.wait_for(iterator.aclose(), timeout=1)
    await asyncio.sleep(0.2)
