from typing import Any, Optional
from port_ocean.cache.base import CacheProvider
from port_ocean.cache.errors import FailedToReadCacheError, FailedToWriteCacheError
from port_ocean.core.models import CachingStorageMode


class FailedToReadCacheMemoryError(FailedToReadCacheError):
    pass


class FailedToWriteCacheMemoryError(FailedToWriteCacheError):
    pass


class InMemoryCacheProvider(CacheProvider):
    CACHE_KEY = "cache"
    STORAGE_TYPE = CachingStorageMode.memory

    def __init__(self, caching_storage: dict[str, Any] | None = None) -> None:
        self._storage = caching_storage or {}
        self._storage[self.CACHE_KEY] = self._storage.get(self.CACHE_KEY, {})

    async def get(self, key: str) -> Optional[Any]:
        try:
            return self._storage.get(self.CACHE_KEY, {}).get(key)
        except KeyError as e:
            raise FailedToReadCacheMemoryError(f"Failed to read cache: {str(e)}")

    async def set(self, key: str, value: Any) -> None:
        try:
            self._storage[self.CACHE_KEY][key] = value
        except KeyError as e:
            raise FailedToWriteCacheMemoryError(f"Failed to write cache: {str(e)}")

    async def clear(self) -> None:
        self._storage[self.CACHE_KEY].clear()
