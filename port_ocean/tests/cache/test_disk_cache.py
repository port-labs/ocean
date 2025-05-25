import os
import pytest
from pathlib import Path

from port_ocean.cache.disk import (
    DiskCacheProvider,
    FailedToReadCacheFileError,
    FailedToWriteCacheFileError,
)


@pytest.fixture
def disk_cache(tmp_path: Path) -> DiskCacheProvider:
    """Fixture that provides a DiskCacheProvider with a temporary directory."""
    return DiskCacheProvider(cache_dir=str(tmp_path))


@pytest.mark.asyncio
async def test_disk_cache_set_get(disk_cache: DiskCacheProvider) -> None:
    """Test setting and getting values from disk cache."""
    # Test basic set/get
    await disk_cache.set("test_key", "test_value")
    assert await disk_cache.get("test_key") == "test_value"

    # Test with different types
    test_data = {
        "string": "hello",
        "int": 42,
        "float": 3.14,
        "list": [1, 2, 3],
        "dict": {"a": 1, "b": 2},
    }

    for key, value in test_data.items():
        await disk_cache.set(key, value)
        assert await disk_cache.get(key) == value


@pytest.mark.asyncio
async def test_disk_cache_clear(disk_cache: DiskCacheProvider) -> None:
    """Test clearing all values from disk cache."""
    # Add multiple values
    for i in range(5):
        await disk_cache.set(f"key_{i}", f"value_{i}")

    # Verify values exist
    for i in range(5):
        assert await disk_cache.get(f"key_{i}") == f"value_{i}"

    # Clear cache
    await disk_cache.clear()

    # Verify all values are gone
    for i in range(5):
        assert await disk_cache.get(f"key_{i}") is None


@pytest.mark.asyncio
async def test_disk_cache_nonexistent_key(disk_cache: DiskCacheProvider) -> None:
    """Test getting a nonexistent key from disk cache."""
    assert await disk_cache.get("nonexistent_key") is None


@pytest.mark.asyncio
async def test_disk_cache_corrupted_file(
    disk_cache: DiskCacheProvider, tmp_path: Path
) -> None:
    """Test handling of corrupted cache files."""
    # Create a corrupted pickle file
    cache_path = tmp_path / "test_key.pkl"
    with open(cache_path, "wb") as f:
        f.write(b"invalid pickle data")

    # Attempting to read should raise FailedToReadCacheFileError
    with pytest.raises(FailedToReadCacheFileError):
        await disk_cache.get("test_key")


@pytest.mark.asyncio
async def test_disk_cache_write_error(
    disk_cache: DiskCacheProvider, tmp_path: Path
) -> None:
    """Test handling of write errors."""
    # Make the cache directory read-only
    os.chmod(tmp_path, 0o444)

    # Attempting to write should raise FailedToWriteCacheFileError
    with pytest.raises(FailedToWriteCacheFileError):
        await disk_cache.set("test_key", "test_value")

    # Restore permissions
    os.chmod(tmp_path, 0o755)
