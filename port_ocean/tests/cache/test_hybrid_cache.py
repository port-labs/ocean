import os
import pytest
import time
import pickle
from pathlib import Path

from port_ocean.cache.hybrid import (
    HybridCacheProvider,
    FailedToReadHybridCacheError,
    FailedToWriteHybridCacheError,
)


@pytest.fixture
def temp_cache_file(tmp_path: Path) -> str:
    """Fixture that provides a temporary cache file path."""
    return str(tmp_path / "test_cache.pkl")


@pytest.fixture
def hybrid_cache_provider(temp_cache_file: str) -> HybridCacheProvider:
    """Fixture that provides a HybridCacheProvider with a temporary cache file."""
    return HybridCacheProvider(max_size=100, default_ttl=60, cache_file=temp_cache_file)


# Basic Operations Tests


@pytest.mark.asyncio
async def test_hybrid_cache_basic_set_get(
    hybrid_cache_provider: HybridCacheProvider,
) -> None:
    """Test basic set and get operations."""
    await hybrid_cache_provider.set("test_key", "test_value")
    assert await hybrid_cache_provider.get("test_key") == "test_value"


@pytest.mark.asyncio
async def test_hybrid_cache_different_data_types(
    hybrid_cache_provider: HybridCacheProvider,
) -> None:
    """Test setting and getting different data types."""
    test_data = {
        "string": "hello world",
        "int": 42,
        "float": 3.14159,
        "list": [1, 2, 3, 4, 5],
        "dict": {"a": 1, "b": 2, "nested": {"c": 3}},
        "bool": True,
        "none": None,
    }

    for key, value in test_data.items():
        await hybrid_cache_provider.set(key, value)
        assert await hybrid_cache_provider.get(key) == value


@pytest.mark.asyncio
async def test_hybrid_cache_clear(hybrid_cache_provider: HybridCacheProvider) -> None:
    """Test clearing all values from cache."""
    # Add multiple values
    for i in range(5):
        await hybrid_cache_provider.set(f"key_{i}", f"value_{i}")

    # Verify values exist
    for i in range(5):
        assert await hybrid_cache_provider.get(f"key_{i}") == f"value_{i}"

    # Clear cache
    await hybrid_cache_provider.clear()

    # Verify all values are gone
    for i in range(5):
        assert await hybrid_cache_provider.get(f"key_{i}") is None


@pytest.mark.asyncio
async def test_hybrid_cache_nonexistent_key(
    hybrid_cache_provider: HybridCacheProvider,
) -> None:
    """Test getting a nonexistent key returns None."""
    assert await hybrid_cache_provider.get("nonexistent_key") is None


@pytest.mark.asyncio
async def test_hybrid_cache_update_existing_key(
    hybrid_cache_provider: HybridCacheProvider,
) -> None:
    """Test updating an existing key overwrites the value."""
    await hybrid_cache_provider.set("key", "value1")
    assert await hybrid_cache_provider.get("key") == "value1"

    await hybrid_cache_provider.set("key", "value2")
    assert await hybrid_cache_provider.get("key") == "value2"


# TTL Tests


@pytest.mark.asyncio
async def test_hybrid_cache_with_ttl(
    hybrid_cache_provider: HybridCacheProvider,
) -> None:
    """Test that entries expire after TTL."""
    await hybrid_cache_provider.set("test_key", "test_value", ttl=1)
    assert await hybrid_cache_provider.get("test_key") == "test_value"

    # Wait for TTL to expire
    time.sleep(1.1)
    assert await hybrid_cache_provider.get("test_key") is None


@pytest.mark.asyncio
async def test_hybrid_cache_default_ttl(temp_cache_file: str) -> None:
    """Test that default TTL is applied when no per-key TTL is provided."""
    cache = HybridCacheProvider(max_size=100, default_ttl=1, cache_file=temp_cache_file)

    await cache.set("key_with_default_ttl", "value")
    assert await cache.get("key_with_default_ttl") == "value"

    # Wait for default TTL to expire
    time.sleep(1.1)
    assert await cache.get("key_with_default_ttl") is None


@pytest.mark.asyncio
async def test_hybrid_cache_no_ttl(temp_cache_file: str) -> None:
    """Test that entries without TTL don't expire."""
    cache = HybridCacheProvider(
        max_size=100, default_ttl=60, cache_file=temp_cache_file
    )

    await cache.set("key_no_ttl", "value")
    time.sleep(1)
    assert await cache.get("key_no_ttl") == "value"


@pytest.mark.asyncio
async def test_hybrid_cache_override_default_ttl(temp_cache_file: str) -> None:
    """Test that per-key TTL overrides default TTL."""
    cache = HybridCacheProvider(
        max_size=100, default_ttl=10, cache_file=temp_cache_file
    )

    # Set with custom TTL that expires quickly
    await cache.set("key1", "value1", ttl=1)
    # Set with default TTL (10 seconds)
    await cache.set("key2", "value2")

    time.sleep(1.1)

    # key1 should be expired
    assert await cache.get("key1") is None
    # key2 should still exist
    assert await cache.get("key2") == "value2"


# LRU Eviction Tests


@pytest.mark.asyncio
async def test_hybrid_cache_lru_eviction(temp_cache_file: str) -> None:
    """Test that LRU eviction works when cache exceeds max size."""
    cache = HybridCacheProvider(max_size=3, default_ttl=60, cache_file=temp_cache_file)

    # Add 3 items (at max capacity)
    await cache.set("key1", "value1")
    await cache.set("key2", "value2")
    await cache.set("key3", "value3")

    # All should exist
    assert await cache.get("key1") == "value1"
    assert await cache.get("key2") == "value2"
    assert await cache.get("key3") == "value3"

    # Add 4th item, should evict key1 (least recently used)
    await cache.set("key4", "value4")

    assert await cache.get("key1") is None
    assert await cache.get("key2") == "value2"
    assert await cache.get("key3") == "value3"
    assert await cache.get("key4") == "value4"


@pytest.mark.asyncio
async def test_hybrid_cache_lru_order_on_access(temp_cache_file: str) -> None:
    """Test that accessing a key moves it to the end (most recently used)."""
    cache = HybridCacheProvider(max_size=3, default_ttl=60, cache_file=temp_cache_file)

    await cache.set("key1", "value1")
    await cache.set("key2", "value2")
    await cache.set("key3", "value3")

    # Access key1 to make it most recently used
    await cache.get("key1")

    # Add key4, should evict key2 (now least recently used)
    await cache.set("key4", "value4")

    assert await cache.get("key1") == "value1"  # Still exists
    assert await cache.get("key2") is None  # Evicted
    assert await cache.get("key3") == "value3"
    assert await cache.get("key4") == "value4"


@pytest.mark.asyncio
async def test_hybrid_cache_lru_order_on_update(temp_cache_file: str) -> None:
    """Test that updating a key moves it to the end (most recently used)."""
    cache = HybridCacheProvider(max_size=3, default_ttl=60, cache_file=temp_cache_file)

    await cache.set("key1", "value1")
    await cache.set("key2", "value2")
    await cache.set("key3", "value3")

    # Update key1 to make it most recently used
    await cache.set("key1", "updated_value1")

    # Add key4, should evict key2 (now least recently used)
    await cache.set("key4", "value4")

    assert await cache.get("key1") == "updated_value1"  # Still exists and updated
    assert await cache.get("key2") is None  # Evicted
    assert await cache.get("key3") == "value3"
    assert await cache.get("key4") == "value4"


# Disk Persistence Tests


@pytest.mark.asyncio
async def test_hybrid_cache_persistence_across_instances(temp_cache_file: str) -> None:
    """Test that cache persists across different instances."""
    # Create first instance and add data
    cache1 = HybridCacheProvider(
        max_size=100, default_ttl=60, cache_file=temp_cache_file
    )
    await cache1.set("key1", "value1")
    await cache1.set("key2", {"data": "value2"})

    # Create second instance - should load from disk
    cache2 = HybridCacheProvider(
        max_size=100, default_ttl=60, cache_file=temp_cache_file
    )

    assert await cache2.get("key1") == "value1"
    assert await cache2.get("key2") == {"data": "value2"}


@pytest.mark.asyncio
async def test_hybrid_cache_expired_entries_cleaned_on_load(
    temp_cache_file: str,
) -> None:
    """Test that expired entries are removed when loading from disk."""
    # Create first instance with short TTL
    cache1 = HybridCacheProvider(
        max_size=100, default_ttl=60, cache_file=temp_cache_file
    )
    await cache1.set("key1", "value1", ttl=1)
    await cache1.set("key2", "value2", ttl=None)  # No expiration

    # Wait for key1 to expire
    time.sleep(1.1)

    # Create second instance - should clean expired entries on load
    cache2 = HybridCacheProvider(
        max_size=100, default_ttl=60, cache_file=temp_cache_file
    )

    assert await cache2.get("key1") is None  # Expired and cleaned
    assert await cache2.get("key2") == "value2"  # Still exists


@pytest.mark.asyncio
async def test_hybrid_cache_clear_persists_to_disk(temp_cache_file: str) -> None:
    """Test that clearing cache is persisted to disk."""
    # Create first instance and add data
    cache1 = HybridCacheProvider(
        max_size=100, default_ttl=60, cache_file=temp_cache_file
    )
    await cache1.set("key1", "value1")
    await cache1.clear()

    # Create second instance - should load empty cache
    cache2 = HybridCacheProvider(
        max_size=100, default_ttl=60, cache_file=temp_cache_file
    )

    assert await cache2.get("key1") is None


@pytest.mark.asyncio
async def test_hybrid_cache_no_disk_file(tmp_path: Path) -> None:
    """Test that cache works without disk persistence when cache_file is None."""
    cache = HybridCacheProvider(max_size=100, default_ttl=60, cache_file="")

    await cache.set("key1", "value1")
    assert await cache.get("key1") == "value1"

    # No file should be created
    assert not any(tmp_path.iterdir())


@pytest.mark.asyncio
async def test_hybrid_cache_nonexistent_file_on_init(temp_cache_file: str) -> None:
    """Test that cache initializes properly when cache file doesn't exist."""
    # Ensure file doesn't exist
    if os.path.exists(temp_cache_file):
        os.remove(temp_cache_file)

    cache = HybridCacheProvider(
        max_size=100, default_ttl=60, cache_file=temp_cache_file
    )

    await cache.set("key1", "value1")
    assert await cache.get("key1") == "value1"


# Error Handling Tests


@pytest.mark.asyncio
async def test_hybrid_cache_corrupted_pickle_file(temp_cache_file: str) -> None:
    """Test handling of corrupted pickle file."""
    # Create a corrupted pickle file
    os.makedirs(os.path.dirname(temp_cache_file), exist_ok=True)
    with open(temp_cache_file, "wb") as f:
        f.write(b"invalid pickle data that cannot be unpickled")

    # Should raise FailedToReadHybridCacheError
    with pytest.raises(FailedToReadHybridCacheError):
        HybridCacheProvider(max_size=100, default_ttl=60, cache_file=temp_cache_file)


@pytest.mark.asyncio
async def test_hybrid_cache_invalid_cache_format(temp_cache_file: str) -> None:
    """Test handling of invalid cache format (not OrderedDict)."""
    # Create a pickle file with wrong format
    os.makedirs(os.path.dirname(temp_cache_file), exist_ok=True)
    with open(temp_cache_file, "wb") as f:
        pickle.dump({"not": "ordered_dict"}, f)  # Regular dict, not OrderedDict

    # Should initialize with empty cache (warning logged)
    cache = HybridCacheProvider(
        max_size=100, default_ttl=60, cache_file=temp_cache_file
    )

    # Cache should be empty after handling invalid format
    assert await cache.get("any_key") is None


@pytest.mark.asyncio
async def test_hybrid_cache_write_error(temp_cache_file: str) -> None:
    """Test handling of write errors when saving to disk."""
    cache = HybridCacheProvider(
        max_size=100, default_ttl=60, cache_file=temp_cache_file
    )

    # Make directory read-only to cause write error
    cache_dir = os.path.dirname(temp_cache_file)
    os.makedirs(cache_dir, exist_ok=True)
    os.chmod(cache_dir, 0o444)

    try:
        # Should raise FailedToWriteHybridCacheError
        with pytest.raises(FailedToWriteHybridCacheError):
            await cache.set("test_key", "test_value")
    finally:
        # Restore permissions
        os.chmod(cache_dir, 0o755)


@pytest.mark.asyncio
async def test_hybrid_cache_atomic_write(temp_cache_file: str) -> None:
    """Test that writes use atomic operations with temporary file."""
    cache = HybridCacheProvider(
        max_size=100, default_ttl=60, cache_file=temp_cache_file
    )

    await cache.set("key1", "value1")

    # Verify main file exists
    assert os.path.exists(temp_cache_file)
    # Verify temp file was cleaned up
    assert not os.path.exists(temp_cache_file + ".tmp")


# Edge Cases


@pytest.mark.asyncio
async def test_hybrid_cache_empty_string_key(
    hybrid_cache_provider: HybridCacheProvider,
) -> None:
    """Test that empty string can be used as a key."""
    await hybrid_cache_provider.set("", "empty_key_value")
    assert await hybrid_cache_provider.get("") == "empty_key_value"


@pytest.mark.asyncio
async def test_hybrid_cache_large_value(
    hybrid_cache_provider: HybridCacheProvider,
) -> None:
    """Test storing and retrieving large values."""
    large_value = {"data": "x" * 10000, "list": list(range(1000))}
    await hybrid_cache_provider.set("large_key", large_value)
    assert await hybrid_cache_provider.get("large_key") == large_value


@pytest.mark.asyncio
async def test_hybrid_cache_special_characters_in_key(
    hybrid_cache_provider: HybridCacheProvider,
) -> None:
    """Test that special characters in keys are handled correctly."""
    special_keys = [
        "key:with:colons",
        "key/with/slashes",
        "key.with.dots",
        "key-with-dashes",
        "key_with_underscores",
        "key with spaces",
    ]

    for key in special_keys:
        await hybrid_cache_provider.set(key, f"value_for_{key}")
        assert await hybrid_cache_provider.get(key) == f"value_for_{key}"


@pytest.mark.asyncio
async def test_hybrid_cache_zero_max_size(temp_cache_file: str) -> None:
    """Test cache behavior with max_size=0 (immediate eviction)."""
    cache = HybridCacheProvider(max_size=0, default_ttl=60, cache_file=temp_cache_file)

    await cache.set("key1", "value1")
    # With max_size=0, nothing should stay in cache
    assert len(cache.cache) == 0


@pytest.mark.asyncio
async def test_hybrid_cache_max_size_one(temp_cache_file: str) -> None:
    """Test cache behavior with max_size=1."""
    cache = HybridCacheProvider(max_size=1, default_ttl=60, cache_file=temp_cache_file)

    await cache.set("key1", "value1")
    assert await cache.get("key1") == "value1"

    await cache.set("key2", "value2")
    assert await cache.get("key1") is None  # Evicted
    assert await cache.get("key2") == "value2"
