from typing import Any
import asyncio
from port_ocean.utils import cache  # Import the module where 'event' is used
import pytest
from dataclasses import dataclass, field
from typing import AsyncGenerator, AsyncIterator, List, TypeVar


@dataclass
class EventContext:
    attributes: dict[str, Any] = field(default_factory=dict)


@pytest.fixture
def event() -> EventContext:
    return EventContext()


T = TypeVar("T")


async def collect_iterator_results(iterator: AsyncIterator[List[T]]) -> List[T]:
    results = []
    async for item in iterator:
        results.extend(item)
    return results


@pytest.mark.asyncio
async def test_cache_iterator_result(event: EventContext, monkeypatch: Any) -> None:
    monkeypatch.setattr(cache, "event", event)

    call_count = 0

    @cache.cache_iterator_result()
    async def sample_iterator(x: int) -> AsyncGenerator[List[int], None]:
        nonlocal call_count
        call_count += 1
        for i in range(x):
            await asyncio.sleep(0.1)
            yield [i]

    result1 = await collect_iterator_results(sample_iterator(3))
    assert result1 == [0, 1, 2]
    assert call_count == 1

    result2 = await collect_iterator_results(sample_iterator(3))
    assert result2 == [0, 1, 2]
    assert call_count == 1

    result3 = await collect_iterator_results(sample_iterator(4))
    assert result3 == [0, 1, 2, 3]
    assert call_count == 2


@pytest.mark.asyncio
async def test_cache_iterator_result_with_kwargs(
    event: EventContext, monkeypatch: Any
) -> None:
    monkeypatch.setattr(cache, "event", event)

    call_count = 0

    @cache.cache_iterator_result()
    async def sample_iterator(x: int, y: int = 1) -> AsyncGenerator[List[int], None]:
        nonlocal call_count
        call_count += 1
        for i in range(x * y):
            await asyncio.sleep(0.1)
            yield [i]

    result1 = await collect_iterator_results(sample_iterator(2, y=2))
    assert result1 == [0, 1, 2, 3]
    assert call_count == 1

    result2 = await collect_iterator_results(sample_iterator(2, y=2))
    assert result2 == [0, 1, 2, 3]
    assert call_count == 1

    result3 = await collect_iterator_results(sample_iterator(2, y=3))
    assert result3 == [0, 1, 2, 3, 4, 5]
    assert call_count == 2


@pytest.mark.asyncio
async def test_cache_iterator_result_no_cache(
    event: EventContext, monkeypatch: Any
) -> None:
    monkeypatch.setattr(cache, "event", event)

    call_count = 0

    @cache.cache_iterator_result()
    async def sample_iterator(x: int) -> AsyncGenerator[List[int], None]:
        nonlocal call_count
        call_count += 1
        for i in range(x):
            await asyncio.sleep(0.1)
            yield [i]

    result1 = await collect_iterator_results(sample_iterator(3))
    assert result1 == [0, 1, 2]
    assert call_count == 1

    event.attributes.clear()

    result2 = await collect_iterator_results(sample_iterator(3))
    assert result2 == [0, 1, 2]
    assert call_count == 2


@pytest.mark.asyncio
async def test_cache_coroutine_result(event: EventContext, monkeypatch: Any) -> None:
    monkeypatch.setattr(cache, "event", event)

    call_count = 0

    @cache.cache_coroutine_result()
    async def sample_coroutine(x: int) -> int:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)
        return x * 2

    result1 = await sample_coroutine(2)
    assert result1 == 4
    assert call_count == 1

    result2 = await sample_coroutine(2)
    assert result2 == 4
    assert call_count == 1

    result3 = await sample_coroutine(3)
    assert result3 == 6
    assert call_count == 2


@pytest.mark.asyncio
async def test_cache_coroutine_result_with_kwargs(
    event: EventContext, monkeypatch: Any
) -> None:
    monkeypatch.setattr(cache, "event", event)

    call_count = 0

    @cache.cache_coroutine_result()
    async def sample_coroutine(x: int, y: int = 1) -> int:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)
        return x * y

    result1 = await sample_coroutine(2, y=3)
    assert result1 == 6
    assert call_count == 1

    result2 = await sample_coroutine(2, y=3)
    assert result2 == 6
    assert call_count == 1

    result3 = await sample_coroutine(2, y=4)
    assert result3 == 8
    assert call_count == 2


@pytest.mark.asyncio
async def test_cache_coroutine_result_no_cache(
    event: EventContext, monkeypatch: Any
) -> None:
    monkeypatch.setattr(cache, "event", event)

    call_count = 0

    @cache.cache_coroutine_result()
    async def sample_coroutine(x: int) -> int:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)
        return x * 2

    result1 = await sample_coroutine(2)
    assert result1 == 4
    assert call_count == 1

    event.attributes.clear()

    result2 = await sample_coroutine(2)
    assert result2 == 4
    assert call_count == 2
