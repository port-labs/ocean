import time
from typing import Any, Awaitable, Callable

from loguru import logger


class LakehouseBuffer:
    """Accumulates raw items per kind and flushes them to the lakehouse in
    time-bounded batches.

    A single instance covers exactly one kind within one resync.  Items are
    flushed automatically when `flush_interval_seconds` have elapsed since the
    last flush, and unconditionally when `flush()` is called at the end of the
    kind.  Empty flushes are skipped so no unnecessary HTTP requests are made.
    """

    def __init__(
        self,
        flush_fn: Callable[[list[Any]], Awaitable[None]],
        flush_interval_seconds: float = 10.0,
    ) -> None:
        self._flush_fn = flush_fn
        self._flush_interval = flush_interval_seconds
        self._buffer: list[Any] = []
        self._last_flush_at: float | None = None

    async def add(self, items: list[Any]) -> None:
        """Append items to the buffer, flushing if the interval has elapsed."""
        self._buffer.extend(items)
        now = time.monotonic()
        if self._last_flush_at is None:
            self._last_flush_at = now
        elif now - self._last_flush_at >= self._flush_interval:
            await self._do_flush()

    async def flush(self) -> None:
        """Force-flush all remaining buffered items."""
        await self._do_flush()

    async def _do_flush(self) -> None:
        if not self._buffer:
            return
        items, self._buffer = self._buffer, []
        self._last_flush_at = time.monotonic()
        logger.debug(f"Flushing {len(items)} buffered items to lakehouse")
        await self._flush_fn(items)
