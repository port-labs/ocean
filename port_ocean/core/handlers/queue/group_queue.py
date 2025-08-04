import asyncio
from collections import defaultdict, deque
import time
from typing import Deque, Dict, Optional, Set, TypeVar, Any
from contextvars import ContextVar

from loguru import logger

from .abstract_queue import AbstractQueue

T = TypeVar("T")
MaybeStr = str | None

_NO_GROUP = object()
_current_group: ContextVar[Any] = ContextVar("current_group", default=_NO_GROUP)


class GroupQueue(AbstractQueue[T]):
    """Queue with exclusive processing per group."""

    def __init__(
        self,
        group_key: MaybeStr = None,
        name: MaybeStr = None,
        lock_timeout: float = 300,
    ):
        super().__init__(name)
        self.group_key = group_key
        self._queues: Dict[MaybeStr, Deque[T]] = defaultdict(deque)
        self._locked: Set[MaybeStr] = set()
        self._queue_not_empty = asyncio.Condition()
        self.lock_timeout = lock_timeout
        self._lock_timestamps: Dict[MaybeStr, float] = {}
        self._timeout_task: Optional[asyncio.Task[None]] = None

    async def _background_timeout_check(self) -> None:
        """Periodically release locks that have timed out."""
        while True:
            try:
                await asyncio.sleep(self.lock_timeout / 4)
                async with self._queue_not_empty:
                    await self._release_expired_locks()
            except asyncio.CancelledError:
                break

    def _extract_group_key(self, item: T) -> MaybeStr:
        """Extract the group key from an item."""
        if self.group_key is None:
            return None
        if not hasattr(item, self.group_key):
            raise ValueError(
                f"Item {item!r} lacks attribute '{self.group_key}' required for grouping"
            )
        return getattr(item, self.group_key)

    async def put(self, item: T) -> None:
        """Add item to its group's queue."""
        group_key = self._extract_group_key(item)
        async with self._queue_not_empty:
            self._queues[group_key].append(item)
            self._queue_not_empty.notify_all()

    async def _release_expired_locks(self) -> None:
        """Release locks that have exceeded the timeout."""
        now = time.time()
        expired_groups = []

        for group, timestamp in list(self._lock_timestamps.items()):
            if now - timestamp > self.lock_timeout:
                expired_groups.append(group)
                logger.warning(f"Releasing expired lock for group {group}")
                self._locked.discard(group)
                del self._lock_timestamps[group]

        if expired_groups:
            self._queue_not_empty.notify_all()

    async def get(self) -> T:
        """Get the next item from an unlocked group, locking that group."""
        if self._timeout_task is None or self._timeout_task.done():
            self._timeout_task = asyncio.create_task(self._background_timeout_check())

        async with self._queue_not_empty:
            while True:
                await self._release_expired_locks()

                for group, queue in self._queues.items():
                    if queue and group not in self._locked:
                        self._locked.add(group)
                        self._lock_timestamps[group] = time.time()
                        _current_group.set(group)
                        return queue[0]

                await self._queue_not_empty.wait()

    async def commit(self) -> None:
        """Remove the current item and unlock its group."""
        group = _current_group.get()
        if group is _NO_GROUP:
            logger.warning("commit() called without active get()")
            return

        async with self._queue_not_empty:
            queue = self._queues.get(group)
            if queue:
                queue.popleft()
                if not queue:
                    del self._queues[group]

            self._locked.discard(group)
            self._lock_timestamps.pop(group, None)
            _current_group.set(_NO_GROUP)
            self._queue_not_empty.notify_all()

    async def teardown(self) -> None:
        """Wait until all queues are empty and no groups are locked."""
        async with self._queue_not_empty:
            while any(self._queues.values()) or self._locked:
                await self._queue_not_empty.wait()

        if self._timeout_task and not self._timeout_task.done():
            self._timeout_task.cancel()
            try:
                await self._timeout_task
            except asyncio.CancelledError:
                pass

    async def size(self) -> int:
        """Return total number of items across all groups."""
        async with self._queue_not_empty:
            return sum(len(queue) for queue in self._queues.values())

    async def force_unlock_all(self) -> None:
        """Force unlock all groups."""
        async with self._queue_not_empty:
            self._locked.clear()
            self._lock_timestamps.clear()
            self._queue_not_empty.notify_all()
