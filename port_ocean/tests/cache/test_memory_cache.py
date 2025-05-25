import pytest

from port_ocean.cache.memory import (
    InMemoryCacheProvider,
)


@pytest.fixture
def memory_cache() -> InMemoryCacheProvider:
    """Fixture that provides an InMemoryCacheProvider."""
    return InMemoryCacheProvider()


@pytest.mark.asyncio
async def test_memory_cache_set_get(memory_cache: InMemoryCacheProvider) -> None:
    """Test setting and getting values from memory cache."""
    # Test basic set/get
    await memory_cache.set("test_key", "test_value")
    assert await memory_cache.get("test_key") == "test_value"

    # Test with different types
    test_data = {
        "string": "hello",
        "int": 42,
        "float": 3.14,
        "list": [1, 2, 3],
        "dict": {"a": 1, "b": 2},
    }

    for key, value in test_data.items():
        await memory_cache.set(key, value)
        assert await memory_cache.get(key) == value


@pytest.mark.asyncio
async def test_memory_cache_clear(memory_cache: InMemoryCacheProvider) -> None:
    """Test clearing all values from memory cache."""
    # Add multiple values
    for i in range(5):
        await memory_cache.set(f"key_{i}", f"value_{i}")

    # Verify values exist
    for i in range(5):
        assert await memory_cache.get(f"key_{i}") == f"value_{i}"

    # Clear cache
    await memory_cache.clear()

    # Verify all values are gone
    for i in range(5):
        assert await memory_cache.get(f"key_{i}") is None


@pytest.mark.asyncio
async def test_memory_cache_nonexistent_key(
    memory_cache: InMemoryCacheProvider,
) -> None:
    """Test getting a nonexistent key from memory cache."""
    assert await memory_cache.get("nonexistent_key") is None
