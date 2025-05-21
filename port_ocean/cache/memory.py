from typing import Any, Optional
from port_ocean.cache.base import CacheProvider


class InMemoryCacheProvider(CacheProvider):
    CACHE_KEY = "cache"

    def __init__(self, caching_storage: dict[str, Any] | None = None) -> None:
        self.storage = caching_storage or {}
        self.storage[self.CACHE_KEY] = self.storage.get(self.CACHE_KEY, {})

    async def get(self, key: str) -> Optional[Any]:
        return self.storage.get(self.CACHE_KEY, {}).get(key)

    async def set(self, key: str, value: Any) -> None:
        self.storage[self.CACHE_KEY][key] = value

    async def clear(self) -> None:
        self.storage[self.CACHE_KEY].clear()
