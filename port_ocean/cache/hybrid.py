from typing import Any, Optional

from port_ocean.cache.base import CacheProvider
from port_ocean.cache.errors import FailedToReadCacheError, FailedToWriteCacheError
from port_ocean.core.models import CachingStorageMode


class FailedToReadHybridCacheError(FailedToReadCacheError):
    pass


class FailedToWriteHybridCacheError(FailedToWriteCacheError):
    pass


class HybridCacheProvider(CacheProvider):
    STORAGE_TYPE = CachingStorageMode.hybrid

    def __init__(
        self, disk_cache_provider: CacheProvider, memory_cache_provider: CacheProvider
    ) -> None:
        self._disk_cache_provider = disk_cache_provider
        self._memory_cache_provider = memory_cache_provider

    async def get(self, key: str) -> Optional[Any]:
        try:
            return await self._disk_cache_provider.get(key)
        except FailedToReadCacheError:
            return await self._memory_cache_provider.get(key)
