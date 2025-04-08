from typing import Any
import asyncio
from port_ocean.utils import cache
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


@pytest.mark.asyncio
async def test_conditional_cache_iterator_result_active(
    event: EventContext, monkeypatch: Any
) -> None:
    """
    If the resource is 'active' in the graph, we should store & reuse the iterator's results.
    """
    monkeypatch.setattr(cache, "event", event)

    call_count = 0

    graph = cache.CacheDependencyGraph()
    # Register resource with no dependencies; we want it to stay active.
    # We'll skip the pruning effect by registering a child resource:
    graph.register("MY_RESOURCE")
    graph.register("MY_CHILD", depends_on=["MY_RESOURCE"])
    graph.compute_active(["MY_CHILD"])  # => MY_RESOURCE is also active

    @cache.conditional_cache_iterator_result(graph, "MY_RESOURCE")
    async def sample_iterator(n: int) -> AsyncGenerator[List[int], None]:
        nonlocal call_count
        call_count += 1
        for i in range(n):
            yield [i]

    # First call -> cache miss
    result1 = await collect_iterator_results(sample_iterator(3))
    assert result1 == [0, 1, 2]
    assert call_count == 1
    assert len(event.attributes) == 1  # we stored something in cache

    # Second call -> cache hit
    result2 = await collect_iterator_results(sample_iterator(3))
    assert result2 == [0, 1, 2]
    assert call_count == 1  # not incremented => used cache
    assert len(event.attributes) == 1


@pytest.mark.asyncio
async def test_conditional_cache_iterator_result_inactive(
    event: EventContext, monkeypatch: Any
) -> None:
    """
    If the resource is NOT active, the decorator yields fresh data each time (no caching).
    """
    monkeypatch.setattr(cache, "event", event)

    call_count = 0

    graph = cache.CacheDependencyGraph()
    graph.register("MY_RESOURCE")  # no child depends on it
    # Suppose the user only selected a completely different resource => MY_RESOURCE prunes out
    graph.compute_active(["SOMETHING_ELSE"])
    assert not graph.is_active("MY_RESOURCE")  # => false

    @cache.conditional_cache_iterator_result(graph, "MY_RESOURCE")
    async def sample_iterator(n: int) -> AsyncGenerator[List[int], None]:
        nonlocal call_count
        call_count += 1
        for i in range(n):
            yield [i]

    result1 = await collect_iterator_results(sample_iterator(2))
    assert result1 == [0, 1]
    assert call_count == 1
    assert event.attributes == {}

    # Call again -> no cache => call_count increments
    result2 = await collect_iterator_results(sample_iterator(2))
    assert result2 == [0, 1]
    assert call_count == 2
    assert event.attributes == {}  # no caching was done


@pytest.mark.asyncio
async def test_conditional_cache_coroutine_result_active(
    event: EventContext, monkeypatch: Any
) -> None:
    """
    If the resource is active in the graph, the coroutine's return value is cached.
    """
    monkeypatch.setattr(cache, "event", event)

    call_count = 0

    graph = cache.CacheDependencyGraph()
    # We'll keep MY_RESOURCE active by making something depend on it
    graph.register("MY_RESOURCE")
    graph.register("SOME_CHILD", depends_on=["MY_RESOURCE"])
    graph.compute_active(["SOME_CHILD"])

    @cache.conditional_cache_coroutine_result(graph, "MY_RESOURCE")
    async def sample_coroutine(x: int) -> int:
        nonlocal call_count
        call_count += 1
        return x * 2

    val1 = await sample_coroutine(5)
    assert val1 == 10
    assert call_count == 1
    # Should have stored a single entry in event.attributes
    assert len(event.attributes) == 1

    # Second call with same args => cache hit
    val2 = await sample_coroutine(5)
    assert val2 == 10
    assert call_count == 1  # didn't increment
    assert len(event.attributes) == 1


@pytest.mark.asyncio
async def test_conditional_cache_coroutine_result_inactive(
    event: EventContext, monkeypatch: Any
) -> None:
    """
    If the resource is NOT active, the decorator calls the function each time (no caching).
    """
    monkeypatch.setattr(cache, "event", event)

    call_count = 0

    graph = cache.CacheDependencyGraph()
    graph.register("MY_RESOURCE")
    # Suppose it's pruned => user didn't select it
    graph.compute_active(["ANOTHER_RESOURCE"])
    assert not graph.is_active("MY_RESOURCE")

    @cache.conditional_cache_coroutine_result(graph, "MY_RESOURCE")
    async def sample_coroutine(x: int) -> int:
        nonlocal call_count
        call_count += 1
        return x * 3

    val1 = await sample_coroutine(3)
    assert val1 == 9
    assert call_count == 1
    # No cache set
    assert event.attributes == {}

    val2 = await sample_coroutine(3)
    assert val2 == 9
    # call_count increments => no caching
    assert call_count == 2
    assert event.attributes == {}
