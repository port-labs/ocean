import asyncio
from collections.abc import AsyncIterator

import pytest

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
