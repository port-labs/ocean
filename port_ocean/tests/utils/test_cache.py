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


@pytest.mark.asyncio
async def test_cache_iterator_result_on_instance_method(
    mock_ocean: Any, monkeypatch: Any
) -> None:
    monkeypatch.setattr(cache, "ocean", mock_ocean)

    class Sample:
        def __init__(self) -> None:
            self.calls = 0

        @cache.cache_iterator_result()
        async def inst_method(self, x: int) -> AsyncGenerator[List[int], None]:
            self.calls += 1
            for i in range(x):
                await asyncio.sleep(0.01)
                yield [i]

    s = Sample()

    # First call should MISS and increment calls
    result1 = await collect_iterator_results(s.inst_method(3))
    assert result1 == [0, 1, 2]
    assert s.calls == 1

    # Second call with same args should HIT cache
    result2 = await collect_iterator_results(s.inst_method(3))
    assert result2 == [0, 1, 2]
    assert s.calls == 1  # no extra call

    # Different args should MISS again
    result3 = await collect_iterator_results(s.inst_method(4))
    assert result3 == [0, 1, 2, 3]
    assert s.calls == 2


@pytest.mark.asyncio
async def test_cache_iterator_result_on_class_method(
    mock_ocean: Any, monkeypatch: Any
) -> None:
    monkeypatch.setattr(cache, "ocean", mock_ocean)

    class Sample:
        calls = 0

        @classmethod
        @cache.cache_iterator_result()
        async def cls_method(cls, x: int) -> AsyncGenerator[List[int], None]:
            cls.calls += 1
            for i in range(x):
                await asyncio.sleep(0.01)
                yield [i]

    # First call should MISS
    result1 = await collect_iterator_results(Sample.cls_method(3))
    assert result1 == [0, 1, 2]
    assert Sample.calls == 1

    # Second call with same args should HIT cache
    result2 = await collect_iterator_results(Sample.cls_method(3))
    assert result2 == [0, 1, 2]
    assert Sample.calls == 1

    # Different args should MISS
    result3 = await collect_iterator_results(Sample.cls_method(2))
    assert result3 == [0, 1]
    assert Sample.calls == 2


@pytest.mark.asyncio
async def test_cache_iterator_result_on_static_method(
    mock_ocean: Any, monkeypatch: Any
) -> None:
    monkeypatch.setattr(cache, "ocean", mock_ocean)

    class Sample:
        calls = 0

        @staticmethod
        @cache.cache_iterator_result()
        async def static_method(x: int) -> AsyncGenerator[List[int], None]:
            Sample.calls += 1
            for i in range(x):
                await asyncio.sleep(0.01)
                yield [i]

    # First call should MISS
    result1 = await collect_iterator_results(Sample.static_method(3))
    assert result1 == [0, 1, 2]
    assert Sample.calls == 1

    # Second call with same args should HIT
    result2 = await collect_iterator_results(Sample.static_method(3))
    assert result2 == [0, 1, 2]
    assert Sample.calls == 1

    # Different args should MISS
    result3 = await collect_iterator_results(Sample.static_method(4))
    assert result3 == [0, 1, 2, 3]
    assert Sample.calls == 2


@pytest.mark.asyncio
async def test_regular_iterator_with_self_param_not_filtered(
    mock_ocean: Any, monkeypatch: Any
) -> None:
    """Test that regular iterator functions with 'self' parameter are not filtered (by design)."""
    monkeypatch.setattr(cache, "ocean", mock_ocean)

    async def regular_function_with_self(
        self: int, y: int
    ) -> AsyncGenerator[List[int], None]:
        for i in range(self + y):
            await asyncio.sleep(0.01)
            yield [i]

    # Test that 'self' parameter IS filtered (by design, for consistency)
    key1 = cache.hash_func(regular_function_with_self, 5, y=3)
    key2 = cache.hash_func(regular_function_with_self, 4, y=3)

    # Keys should not be the same because 'self' is not filtered (by design)
    assert key1 != key2


@pytest.mark.asyncio
async def test_cache_coroutine_result_on_instance_method(
    mock_ocean: Any, monkeypatch: Any
) -> None:
    monkeypatch.setattr(cache, "ocean", mock_ocean)

    class Sample:
        def __init__(self) -> None:
            self.calls = 0

        @cache.cache_coroutine_result()
        async def inst_method(self, x: int) -> int:
            self.calls += 1
            await asyncio.sleep(0.01)
            return x * 2

    s = Sample()

    # First call should MISS and increment calls
    result1 = await s.inst_method(3)
    assert result1 == 6
    assert s.calls == 1

    # Second call with same args should HIT cache
    result2 = await s.inst_method(3)
    assert result2 == 6
    assert s.calls == 1  # still 1 call

    # Different args should MISS again
    result3 = await s.inst_method(4)
    assert result3 == 8
    assert s.calls == 2


@pytest.mark.asyncio
async def test_cache_coroutine_result_on_class_method(
    mock_ocean: Any, monkeypatch: Any
) -> None:
    monkeypatch.setattr(cache, "ocean", mock_ocean)

    class Sample:
        calls = 0

        @classmethod
        @cache.cache_coroutine_result()
        async def cls_method(cls, x: int) -> int:
            cls.calls += 1
            await asyncio.sleep(0.01)
            return x + 5

    # First call should MISS
    result1 = await Sample.cls_method(3)
    assert result1 == 8
    assert Sample.calls == 1

    # Second call with same args should HIT
    result2 = await Sample.cls_method(3)
    assert result2 == 8
    assert Sample.calls == 1

    # Different args should MISS
    result3 = await Sample.cls_method(2)
    assert result3 == 7
    assert Sample.calls == 2


@pytest.mark.asyncio
async def test_cache_coroutine_result_on_static_method(
    mock_ocean: Any, monkeypatch: Any
) -> None:
    monkeypatch.setattr(cache, "ocean", mock_ocean)

    class Sample:
        calls = 0

        @staticmethod
        @cache.cache_coroutine_result()
        async def static_method(x: int) -> int:
            Sample.calls += 1
            await asyncio.sleep(0.01)
            return x * x

    # First call should MISS
    result1 = await Sample.static_method(3)
    assert result1 == 9
    assert Sample.calls == 1

    # Second call with same args should HIT
    result2 = await Sample.static_method(3)
    assert result2 == 9
    assert Sample.calls == 1

    # Different args should MISS
    result3 = await Sample.static_method(4)
    assert result3 == 16
    assert Sample.calls == 2


@pytest.mark.asyncio
async def test_regular_coroutine_with_self_param_not_filtered(
    mock_ocean: Any, monkeypatch: Any
) -> None:
    """Test that regular coroutines with 'self' parameter are not filtered (by design)."""
    monkeypatch.setattr(cache, "ocean", mock_ocean)

    @cache.cache_coroutine_result()
    async def regular_function_with_self(self: int, y: int) -> int:
        await asyncio.sleep(0.01)
        return self + y

    key1 = cache.hash_func(regular_function_with_self, 5, y=3)
    key2 = cache.hash_func(regular_function_with_self, 4, y=3)

    # Keys should not be the same because 'self' is not filtered
    assert key1 != key2


@pytest.mark.asyncio
async def test_cache_iterator_maintains_chunks(
    mock_ocean: Any, monkeypatch: Any
) -> None:
    monkeypatch.setattr(cache, "ocean", mock_ocean)

    call_count = 0

    @cache.cache_iterator_result()
    async def chunked_iterator() -> AsyncGenerator[List[int], None]:
        nonlocal call_count
        call_count += 1
        yield [1, 2]
        await asyncio.sleep(0.01)
        yield [3, 4]

    # First call - populates cache
    results1 = []
    async for chunk in chunked_iterator():
        results1.append(chunk)

    assert results1 == [[1, 2], [3, 4]]
    assert call_count == 1

    # Second call - reads from cache
    results2 = []
    async for chunk in chunked_iterator():
        results2.append(chunk)

    # Verify structure is preserved (chunks remain separate)
    assert results2 == [[1, 2], [3, 4]]
    assert call_count == 1
