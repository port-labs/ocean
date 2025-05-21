from abc import ABC, abstractmethod
from typing import Any, Optional


class CacheProvider(ABC):
    """Base class for cache providers that defines the contract for all cache implementations."""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache."""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any) -> None:
        """Set a value in the cache."""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all values from the cache."""
        pass
