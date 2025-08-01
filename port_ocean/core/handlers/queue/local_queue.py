import asyncio
from typing import TypeVar

from .abstract_queue import AbstractQueue

T = TypeVar("T")


class LocalQueue(AbstractQueue[T]):
    """Implementation of Queue using asyncio.Queue"""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[T] = asyncio.Queue()

    async def put(self, item: T) -> None:
        await self._queue.put(item)

    async def get(self) -> T:
        return await self._queue.get()

    async def teardown(self) -> None:
        await self._queue.join()

    async def commit(self) -> None:
        self._queue.task_done()

    async def size(self) -> int:
        return self._queue.qsize()
