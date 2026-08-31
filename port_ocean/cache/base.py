from abc import ABC, abstractmethod
from typing import Any

from port_ocean.core.models import CachingStorageMode


class CacheProvider(ABC):
    """Base class for cache providers that defines the contract for all cache implementations."""

    STORAGE_TYPE: CachingStorageMode

    @abstractmethod
    async def get(self, key: str) -> Any | None:
        """Get a value from the cache."""

    @abstractmethod
    async def set(self, key: str, value: Any) -> None:
        """Set a value in the cache."""

    @abstractmethod
    async def clear(self) -> None:
        """Clear all values from the cache."""
