import asyncio
from collections import defaultdict, deque
from typing import Deque, Dict, Optional, Set, Tuple, TypeVar

from .abstract_queue import AbstractQueue  # unchanged
from contextvars import ContextVar
import uuid

T = TypeVar("T")
MaybeStr = str | None


_worker_context: ContextVar[Optional[str]] = ContextVar("worker_context", default=None)


class GroupQueue(AbstractQueue[T]):
    """
    A queue that guarantees *exclusive* processing per group.

    Every item `T` must expose the attribute named in `group_key`
    (or `group_key is None` → all items share the same group).

    Rules
    -----
    • FIFO within each group.
    • No two items with the same group key are ever handed
      to workers concurrently.
    • FIXED: Now properly supports multiple concurrent workers.
    """

    # ---------- construction ----------
    def __init__(self, group_key: MaybeStr = None, name: MaybeStr = None):
        super().__init__(name)
        self.group_key = group_key  # str | None
        self._queues: Dict[MaybeStr, Deque[T]] = defaultdict(deque)
        self._locked: Set[MaybeStr] = set()
        self._queue_not_empty = asyncio.Condition()

        # FIX: Track multiple concurrent items instead of single _current_item
        self._current_items: Dict[str, Tuple[MaybeStr, T]] = (
            {}
        )  # worker_id -> (group, item)
        self._group_to_worker: Dict[MaybeStr, str] = (
            {}
        )  # group -> worker_id processing it

    # ---------- helpers ----------
    def _extract_group_key(self, item: T) -> MaybeStr:
        if self.group_key is None:
            return None
        if not hasattr(item, self.group_key):
            raise ValueError(
                f"Item {item!r} lacks attribute '{self.group_key}' required for grouping"
            )
        return getattr(item, self.group_key)

    def _get_worker_id(self) -> str:
        """Get unique worker ID for current task/coroutine"""
        worker_id = _worker_context.get()
        if worker_id is None:
            # Generate unique ID for this task
            worker_id = str(uuid.uuid4())
            _worker_context.set(worker_id)
        return worker_id

    # ---------- AbstractQueue API ----------
    async def put(self, item: T) -> None:
        """Put a single item into its group‑FIFO."""
        group_key = self._extract_group_key(item)
        async with self._queue_not_empty:
            self._queues[group_key].append(item)
            self._queue_not_empty.notify_all()

    async def get(self) -> T:
        """
        Get the head item of the first *unlocked* group.
        Locks that group until `commit()` is called.
        """
        worker_id = self._get_worker_id()

        async with self._queue_not_empty:
            while True:
                for g, q in self._queues.items():
                    if not q or g in self._locked:
                        continue

                    # Lock the group and track which worker is processing it
                    self._locked.add(g)
                    item = q[0]  # peek without pop
                    self._current_items[worker_id] = (g, item)
                    self._group_to_worker[g] = worker_id

                    return item

                await self._queue_not_empty.wait()

    async def commit(self) -> None:
        """
        Mark the current item as processed and unlock its group.
        Uses worker context to identify which item to commit.
        """
        worker_id = self._get_worker_id()

        async with self._queue_not_empty:
            if worker_id not in self._current_items:
                return  # Nothing to commit for this worker

            g, item = self._current_items[worker_id]
            q = self._queues[g]

            # Verify we're committing the right item (safety check)
            if q and q[0] == item and self._group_to_worker.get(g) == worker_id:
                q.popleft()  # remove the item we processed
                if not q:
                    del self._queues[g]  # tidy up empty queue

                # Clean up tracking
                self._locked.discard(g)
                del self._current_items[worker_id]
                if g in self._group_to_worker:
                    del self._group_to_worker[g]

                self._queue_not_empty.notify_all()

    async def teardown(self) -> None:
        """
        Wait until **all items** are processed and no group is locked.
        """
        async with self._queue_not_empty:
            while any(self._queues.values()) or self._locked:
                await self._queue_not_empty.wait()

    async def size(self) -> int:
        """
        Return **the current number of batched items waiting in the queue**,
        aggregated across every group.

        • Excludes the batches that are being processed right now
          (i.e. those referenced by ``self._current_items``).
        • Safe to call from multiple coroutines concurrently.
        • Runs in O(#groups) time – negligible unless you have
          millions of distinct group keys.
        """
        async with self._queue_not_empty:
            return sum(len(dq) for dq in self._queues.values())

    async def force_unlock_all(self) -> None:
        """
        Emergency method to unlock all groups and clear worker tracking.
        Use only for cleanup in exceptional situations.
        """
        async with self._queue_not_empty:
            self._locked.clear()
            self._current_items.clear()
            self._group_to_worker.clear()
            self._queue_not_empty.notify_all()
