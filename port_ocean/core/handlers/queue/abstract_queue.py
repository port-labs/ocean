from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")


class AbstractQueue(ABC, Generic[T]):
    """Abstract interface for queues"""

    def __init__(self, name: str | None = None):
        pass

    @abstractmethod
    async def put(self, item: T) -> None:
        """Put an item into the queue"""
        pass

    @abstractmethod
    async def get(self) -> T:
        """Get an item from the queue"""
        pass

    @abstractmethod
    async def teardown(self) -> None:
        """Wait for all items to be processed"""
        pass

    @abstractmethod
    async def size(self) -> int:
        """Size of the queue"""
        pass

    @abstractmethod
    async def commit(self) -> None:
        """Mark item as processed"""
        pass
