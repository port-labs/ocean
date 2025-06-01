from typing import Any
import asyncio
from port_ocean.utils import cache
import pytest
from typing import AsyncGenerator, AsyncIterator, List, TypeVar
from unittest.mock import AsyncMock
from port_ocean.cache.errors import FailedToReadCacheError, FailedToWriteCacheError
from port_ocean.cache.memory import InMemoryCacheProvider


@pytest.fixture
def memory_cache() -> InMemoryCacheProvider:
    return InMemoryCacheProvider()


@pytest.fixture
def mock_ocean(memory_cache: InMemoryCacheProvider) -> Any:
    return type(
        "MockOcean",
        (),
        {"app": type("MockApp", (), {"cache_provider": memory_cache})()},
    )()


T = TypeVar("T")


async def collect_iterator_results(iterator: AsyncIterator[List[T]]) -> List[T]:
    results = []
    async for item in iterator:
        results.extend(item)
    return results


@pytest.mark.asyncio
async def test_cache_iterator_result(mock_ocean: Any, monkeypatch: Any) -> None:
    monkeypatch.setattr(cache, "ocean", mock_ocean)

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
    mock_ocean: Any, monkeypatch: Any
) -> None:
    monkeypatch.setattr(cache, "ocean", mock_ocean)

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
async def test_cache_iterator_result_cache_errors(
    mock_ocean: Any, monkeypatch: Any
) -> None:
    # Create a mock cache provider that raises errors
    mock_cache_provider = AsyncMock()
    mock_cache_provider.get.side_effect = FailedToReadCacheError("fail read")
    mock_cache_provider.set.side_effect = FailedToWriteCacheError("fail write")

    mock_ocean.app.cache_provider = mock_cache_provider
    monkeypatch.setattr(cache, "ocean", mock_ocean)

    call_count = 0

    @cache.cache_iterator_result()
    async def sample_iterator(x: int) -> AsyncGenerator[List[int], None]:
        nonlocal call_count
        call_count += 1
        for i in range(x):
            await asyncio.sleep(0.1)
            yield [i]

    # First call should execute the function since cache read fails
    result1 = await collect_iterator_results(sample_iterator(3))
    assert result1 == [0, 1, 2]
    assert call_count == 1

    # Second call should also execute the function since cache read fails
    result2 = await collect_iterator_results(sample_iterator(3))
    assert result2 == [0, 1, 2]
    assert call_count == 2


@pytest.mark.asyncio
async def test_cache_coroutine_result(mock_ocean: Any, monkeypatch: Any) -> None:
    monkeypatch.setattr(cache, "ocean", mock_ocean)

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
    mock_ocean: Any, monkeypatch: Any
) -> None:
    monkeypatch.setattr(cache, "ocean", mock_ocean)

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
async def test_cache_coroutine_result_cache_errors(
    mock_ocean: Any, monkeypatch: Any
) -> None:
    # Create a mock cache provider that raises errors
    mock_cache_provider = AsyncMock()
    mock_cache_provider.get.side_effect = FailedToReadCacheError("fail read")
    mock_cache_provider.set.side_effect = FailedToWriteCacheError("fail write")

    mock_ocean.app.cache_provider = mock_cache_provider
    monkeypatch.setattr(cache, "ocean", mock_ocean)

    call_count = 0

    @cache.cache_coroutine_result()
    async def sample_coroutine(x: int) -> int:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)
        return x * 2

    # First call should execute the function since cache read fails
    result1 = await sample_coroutine(2)
    assert result1 == 4
    assert call_count == 1

    # Second call should also execute the function since cache read fails
    result2 = await sample_coroutine(2)
    assert result2 == 4
    assert call_count == 2


@pytest.mark.asyncio
async def test_cache_failures_dont_affect_execution(
    mock_ocean: Any, monkeypatch: Any
) -> None:
    """Test that cache failures (both read and write) don't affect the decorated function execution."""
    # Create a mock cache provider that raises errors
    mock_cache_provider = AsyncMock()
    mock_cache_provider.get.side_effect = FailedToReadCacheError("fail read")
    mock_cache_provider.set.side_effect = FailedToWriteCacheError("fail write")

    mock_ocean.app.cache_provider = mock_cache_provider
    monkeypatch.setattr(cache, "ocean", mock_ocean)

    # Test both iterator and coroutine decorators
    iterator_call_count = 0
    coroutine_call_count = 0

    @cache.cache_iterator_result()
    async def sample_iterator(x: int) -> AsyncGenerator[List[int], None]:
        nonlocal iterator_call_count
        iterator_call_count += 1
        for i in range(x):
            await asyncio.sleep(0.1)
            yield [i]

    @cache.cache_coroutine_result()
    async def sample_coroutine(x: int) -> int:
        nonlocal coroutine_call_count
        coroutine_call_count += 1
        await asyncio.sleep(0.1)
        return x * 2

    # Test iterator function
    # First call - should execute function (cache read fails)
    result1 = await collect_iterator_results(sample_iterator(3))
    assert result1 == [0, 1, 2]
    assert iterator_call_count == 1
    assert mock_cache_provider.get.call_count == 1
    assert mock_cache_provider.set.call_count == 1

    # Second call - should execute function again (cache read fails)
    result2 = await collect_iterator_results(sample_iterator(3))
    assert result2 == [0, 1, 2]
    assert iterator_call_count == 2
    assert mock_cache_provider.get.call_count == 2
    assert mock_cache_provider.set.call_count == 2

    # Test coroutine function
    # First call - should execute function (cache read fails)
    result3 = await sample_coroutine(4)
    assert result3 == 8
    assert coroutine_call_count == 1
    assert mock_cache_provider.get.call_count == 3
    assert mock_cache_provider.set.call_count == 3

    # Second call - should execute function again (cache read fails)
    result4 = await sample_coroutine(4)
    assert result4 == 8
    assert coroutine_call_count == 2
    assert mock_cache_provider.get.call_count == 4
    assert mock_cache_provider.set.call_count == 4

    # Verify that both read and write errors were raised
    assert isinstance(mock_cache_provider.get.side_effect, FailedToReadCacheError)
    assert isinstance(mock_cache_provider.set.side_effect, FailedToWriteCacheError)
