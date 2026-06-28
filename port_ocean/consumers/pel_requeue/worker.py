"""PEL (Pending Entry List) requeue worker.

All pods run the scan concurrently. XAUTOCLAIM is a single atomic Redis
command, so only one pod will ever claim a given stuck message; redundant
scans by other pods are harmless no-ops.

The worker itself contains no processing logic — consumer pods handle all
actual processing.  When a message has been stuck in the PEL longer than
``stuck_timeout_ms`` the worker:

1. Claims it with XAUTOCLAIM.
2. If ``requeue_count`` has reached ``max_requeue_count``, ACKs and discards it.
3. Otherwise increments ``requeue_count``, re-enqueues via XADD, then ACKs the
   original entry to remove it from the PEL.
"""

import asyncio
from typing import Any, cast

from loguru import logger
from redis.asyncio import Redis

from port_ocean.consumers.pel_requeue.settings import (
    PELRequeueWorkerSettings,
    _PEL_CONSUMER_NAME,
)


class PELRequeueWorker:
    """Background worker that rescues messages stuck in the Redis PEL.

    Every pod runs the scan independently on a fixed interval. XAUTOCLAIM
    atomicity ensures each stuck message is claimed and processed by exactly
    one pod even when multiple pods scan concurrently.
    """

    def __init__(self, redis: Redis, settings: PELRequeueWorkerSettings) -> None:
        self._redis = redis
        self._settings = settings
        self._is_running = False
        self._lifecycle_task: asyncio.Task[None] | None = None

    @property
    def _stream_key(self) -> str:
        return self._settings.stream_key

    @property
    def _consumer_group(self) -> str:
        return self._settings.consumer_group

    async def start(self) -> None:
        self._is_running = True
        self._lifecycle_task = asyncio.create_task(self._worker_loop())
        logger.info(
            "PEL requeue worker started",
            stream_key=self._stream_key,
            consumer_group=self._consumer_group,
        )

    async def stop(self) -> None:
        self._is_running = False
        if self._lifecycle_task is not None:
            self._lifecycle_task.cancel()
            await asyncio.gather(self._lifecycle_task, return_exceptions=True)
            self._lifecycle_task = None

    async def _worker_loop(self) -> None:
        while self._is_running:
            try:
                await self._scan_and_requeue()
                await asyncio.sleep(self._settings.scan_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as error:
                logger.exception(
                    "Unexpected error in PEL requeue worker loop",
                    error=str(error),
                )
                await asyncio.sleep(self._settings.lifecycle_error_backoff_seconds)

    async def _scan_and_requeue(self) -> None:
        """Paginate through all PEL entries idle beyond the stuck threshold."""
        cursor = "0-0"
        total_processed = 0

        while True:
            result = await self._redis.xautoclaim(
                self._stream_key,
                self._consumer_group,
                _PEL_CONSUMER_NAME,
                self._settings.stuck_timeout_ms,
                cursor,
                count=self._settings.xautoclaim_count,
            )

            if not result:
                break

            next_cursor: str = result[0]
            messages: list[tuple[str, dict[str, str]]] = (
                result[1] if len(result) > 1 else []
            )

            for message_id, fields in messages:
                await self._handle_stuck_message(message_id, fields)
                total_processed += 1

            if next_cursor == "0-0" or not messages:
                break

            cursor = next_cursor

        if total_processed > 0:
            logger.info(
                "PEL requeue scan complete",
                total_processed=total_processed,
                stream_key=self._stream_key,
            )

    async def _handle_stuck_message(
        self, message_id: str, fields: dict[str, str]
    ) -> None:
        requeue_count = int(fields.get("requeue_count", "0"))
        max_requeue_count = self._settings.max_requeue_count

        if requeue_count >= max_requeue_count:
            logger.warning(
                "Discarding stuck message: requeue_count exceeded threshold",
                message_id=message_id,
                requeue_count=requeue_count,
                max_requeue_count=max_requeue_count,
                stream_key=self._stream_key,
            )
            await self._redis.xack(self._stream_key, self._consumer_group, message_id)
            return

        new_fields = dict(fields)
        new_fields["requeue_count"] = str(requeue_count + 1)

        async with self._redis.pipeline(transaction=True) as pipe:
            await pipe.xadd(self._stream_key, cast(Any, new_fields))
            await pipe.xack(self._stream_key, self._consumer_group, message_id)
            await pipe.execute()

        logger.info(
            "Requeued stuck PEL message",
            original_message_id=message_id,
            new_requeue_count=requeue_count + 1,
            stream_key=self._stream_key,
        )
