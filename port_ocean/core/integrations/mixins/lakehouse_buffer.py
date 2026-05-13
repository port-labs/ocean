import json
import time
from typing import Any
import uuid

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import LakehouseDataEntry, LakehouseDataEntryBatch, LakehouseEventType

_DEFAULT_MAX_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB


class LakehouseBuffer:
    """Accumulates raw items per kind and flushes them to the lakehouse in
    time-bounded, size-bounded batches.

    A single instance covers exactly one kind within one resync.  Items are
    flushed automatically when either condition is met:
      - ``flush_interval_seconds`` have elapsed since the last flush, OR
      - the estimated JSON size of the buffer reaches ``max_size_bytes``.

    Flushing is also forced unconditionally when ``flush()`` is called at the
    end of the kind.  Empty flushes are skipped so no unnecessary HTTP requests
    are made.
    """

    def __init__(
        self,
        sync_id: str,
        kind: str,
        resync_start_time: Any,
        flush_interval_seconds: float = 10.0,
        max_size_bytes: int = _DEFAULT_MAX_SIZE_BYTES,
        event_type: LakehouseEventType = LakehouseEventType.RESYNC,
    ) -> None:
        self._flush_interval = flush_interval_seconds
        self._max_size_bytes = max_size_bytes
        self._buffer: list[Any] = []
        self._current_size_bytes: int = 0
        self._last_flush_at: float | None = None
        self.sync_id = sync_id
        self.kind = kind
        self.resync_start_time = resync_start_time
        self.event_type = event_type

    async def flush(self) -> None:
        if not self._buffer:
            return
        logger.debug(
            f"Flushing {len(self._buffer)} buffered batch items to lakehouse"
            f" (~{self._current_size_bytes / (1024 * 1024):.1f} MB)"
        )
        event_id = str(uuid.uuid4())
        event = LakehouseDataEntryBatch(
            event_id=event_id,
            type=self.event_type.value,
            kind=self.kind,
            event_type=self.event_type,
            resync_start_time=self.resync_start_time,
            extraction_timestamp=int(time.time() * 1000),
            data=self._buffer,
        )
        await ocean.port_client.post_integration_raw_data_batch(
            self.sync_id,
            event,
        )
        self._buffer = []
        self._current_size_bytes = 0
        self._last_flush_at = time.monotonic()

    async def add(self, batch_items: LakehouseDataEntry) -> None:
        """Append items to the buffer, flushing if the interval or size cap is reached."""
        self._buffer.append(batch_items)
        self._current_size_bytes += len(json.dumps(batch_items).encode("utf-8"))

        now = time.monotonic()
        if self._last_flush_at is None:
            self._last_flush_at = now
            return

        interval_exceeded = now - self._last_flush_at >= self._flush_interval
        size_exceeded = self._current_size_bytes >= self._max_size_bytes

        if interval_exceeded or size_exceeded:
            if size_exceeded:
                logger.debug(
                    f"Lakehouse buffer size cap reached"
                    f" ({self._current_size_bytes / (1024 * 1024):.1f} MB >= "
                    f"{self._max_size_bytes / (1024 * 1024):.0f} MB), flushing"
                )
            await self.flush()

