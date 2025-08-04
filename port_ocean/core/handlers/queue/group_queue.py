import asyncio
from collections import defaultdict, deque
import time
from typing import Deque, Dict, Optional, Set, Tuple, TypeVar

from loguru import logger

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
    """

    # ---------- construction ----------
    def __init__(
        self,
        group_key: MaybeStr = None,
        name: MaybeStr = None,
        lock_timeout: float = 300,
    ):
        super().__init__(name)
        self.group_key = group_key  # str | None
        self._queues: Dict[MaybeStr, Deque[T]] = defaultdict(deque)
        self._locked: Set[MaybeStr] = set()
        self._queue_not_empty = asyncio.Condition()
        self.lock_timeout = lock_timeout
        self._lock_timestamps: Dict[MaybeStr, float] = {}
        self._timeout_task: asyncio.Task[None] | None = None

        self._current_items: Dict[str, Tuple[MaybeStr, T]] = (
            {}
        )  # worker_id -> (group, item)
        self._group_to_worker: Dict[MaybeStr, str] = (
            {}
        )  # group -> worker_id processing it

    async def _background_timeout_check(self) -> None:
        """Actively check for expired locks every N seconds"""
        while True:
            try:
                await asyncio.sleep(self.lock_timeout / 4)  # Check frequently
                async with self._queue_not_empty:
                    await self._release_expired_locks()  # This will notify_all() if needed
            except asyncio.CancelledError:
                break

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
        """Get stable worker ID based on current task"""
        task = asyncio.current_task()
        return f"worker-{id(task)}" if task else f"fallback-{uuid.uuid4()}"

    # ---------- AbstractQueue API ----------
    async def put(self, item: T) -> None:
        """Put a single item into its group‑FIFO."""
        group_key = self._extract_group_key(item)
        async with self._queue_not_empty:
            self._queues[group_key].append(item)
            self._queue_not_empty.notify_all()

    async def _release_expired_locks(self) -> None:
        """Release locks older than timeout"""
        now = time.time()
        expired_groups = []

        for group, timestamp in self._lock_timestamps.items():
            if now - timestamp > self.lock_timeout:
                expired_groups.append(group)

        for group in expired_groups:
            logger.warning(f"Releasing expired lock for group {group}")
            self._locked.discard(group)
            self._lock_timestamps.pop(group, None)

            # Clean up worker tracking
            worker_to_remove = None
            for worker_id, (g, item) in self._current_items.items():
                if g == group:
                    worker_to_remove = worker_id
                    break

            if worker_to_remove:
                del self._current_items[worker_to_remove]
                self._group_to_worker.pop(group, None)
        # CRITICAL: Notify waiting workers that locks were released
        if expired_groups:
            self._queue_not_empty.notify_all()

    async def get(self) -> T:
        """
        Get the head item of the first *unlocked* group.
        Locks that group until `commit()` is called.
        """

        if self._timeout_task is None or self._timeout_task.done():
            self._timeout_task = asyncio.create_task(self._background_timeout_check())

        worker_id = self._get_worker_id()

        async with self._queue_not_empty:
            while True:

                await self._release_expired_locks()

                for g, q in self._queues.items():
                    if not q or g in self._locked:
                        continue

                    # Lock the group and track which worker is processing it
                    self._locked.add(g)
                    item = q[0]  # peek without pop
                    self._current_items[worker_id] = (g, item)
                    self._lock_timestamps[g] = time.time()
                    self._group_to_worker[g] = worker_id

                    return item

                await self._queue_not_empty.wait()

    async def commit(self) -> None:
        worker_id = self._get_worker_id()

        async with self._queue_not_empty:
            if worker_id not in self._current_items:
                logger.warning(
                    f"Worker {worker_id} attempted commit with no current item"
                )
                return

            g, item = self._current_items[worker_id]

            try:
                q = self._queues.get(g)
                if q and q[0] == item:
                    q.popleft()
                    if not q:
                        del self._queues[g]
                else:
                    logger.warning(
                        f"Queue state mismatch for group {g}, forcing cleanup"
                    )

            except Exception as e:
                logger.error(f"Error during queue cleanup for group {g}: {e}")

            finally:
                self._locked.discard(g)
                self._lock_timestamps.pop(g, None)

                del self._current_items[worker_id]
                self._group_to_worker.pop(g, None)

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
