"""Redis stream maintenance worker.

All pods run the scan concurrently. XAUTOCLAIM is a single atomic Redis
command, so only one pod will ever claim a given stuck message; redundant
scans by other pods are harmless no-ops.

The worker reclaims stuck PEL entries and performs consumer-group hygiene.
Stream consumer pods handle all actual message processing. When a message has
been stuck in the PEL longer than ``stuck_timeout_ms`` the worker:

1. Claims it with XAUTOCLAIM.
2. If ``requeue_count`` has reached ``max_requeue_count``, ACKs and discards it.
3. Otherwise increments ``requeue_count``, re-enqueues via XADD, then ACKs the
   original entry to remove it from the PEL.

After each scan, the worker may also remove idle consumers from the group that
have no pending messages (see ``stream_maintenance_consumer_cleanup_enabled``).
"""

import asyncio

from loguru import logger
from redis.exceptions import ResponseError

from port_ocean.config.settings import LiveEventsRedisSettings
from port_ocean.consumers.redis_client import RedisClient
from port_ocean.consumers.redis_stream_utils import (
    ack_and_finalize_stream_entry,
    cleanup_idle_consumers_from_group,
    ensure_consumer_group,
    is_missing_stream_or_group_error,
    requeue_stream_entry,
)
from port_ocean.consumers.stream_maintenance.settings import (
    STREAM_MAINTENANCE_CONSUMER_NAME,
)


class RedisStreamMaintenanceWorker:
    """Background worker for Redis stream consumer-group maintenance.

    Every pod runs the scan independently on a fixed interval. XAUTOCLAIM
    atomicity ensures each stuck message is claimed and processed by exactly
    one pod even when multiple pods scan concurrently.
    """

    def __init__(
        self,
        redis: RedisClient,
        redis_settings: LiveEventsRedisSettings,
        stream_key: str,
        consumer_group: str,
        *,
        stream_consumer_name: str | None = None,
    ) -> None:
        self._redis = redis
        self._redis_settings = redis_settings
        self._stream_key = stream_key
        self._consumer_group = consumer_group
        self._protected_consumer_names = (
            frozenset({STREAM_MAINTENANCE_CONSUMER_NAME, stream_consumer_name})
            if stream_consumer_name
            else frozenset({STREAM_MAINTENANCE_CONSUMER_NAME})
        )
        self._is_running = False
        self._lifecycle_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self._is_running = True
        self._lifecycle_task = asyncio.create_task(self._worker_loop())
        logger.info(
            "Redis stream maintenance worker started",
            stream_key=self._stream_key,
            consumer_group=self._consumer_group,
        )

    async def stop(self) -> None:
        self._is_running = False
        if self._lifecycle_task is not None:
            self._lifecycle_task.cancel()
            await asyncio.gather(self._lifecycle_task, return_exceptions=True)
            self._lifecycle_task = None

    async def _recover_missing_stream(self) -> None:
        try:
            logger.warning(
                "Redis stream or consumer group missing in stream maintenance worker, recreating",
                stream_key=self._stream_key,
                consumer_group=self._consumer_group,
            )
            await ensure_consumer_group(
                self._redis,
                stream_key=self._stream_key,
                consumer_group=self._consumer_group,
                stream_ttl_seconds=self._redis_settings.stream_ttl_seconds,
            )
        except Exception as recovery_error:
            logger.exception(
                "Failed to recreate Redis stream consumer group "
                "from stream maintenance worker",
                stream_key=self._stream_key,
                error=str(recovery_error),
            )

    async def _worker_loop(self) -> None:
        while self._is_running:
            try:
                await self._scan_and_requeue()
                if self._redis_settings.stream_maintenance_consumer_cleanup_enabled:
                    await self._cleanup_idle_consumers()
                await asyncio.sleep(
                    self._redis_settings.stream_maintenance_scan_interval_seconds
                )
            except asyncio.CancelledError:
                break
            except ResponseError as error:
                if is_missing_stream_or_group_error(error):
                    await self._recover_missing_stream()
                else:
                    logger.exception(
                        "Unexpected Redis error in stream maintenance worker loop",
                        stream_key=self._stream_key,
                        error=str(error),
                    )
                await asyncio.sleep(
                    self._redis_settings.stream_maintenance_error_backoff_seconds
                )
            except Exception as error:
                logger.exception(
                    "Unexpected error in stream maintenance worker loop",
                    error=str(error),
                )
                await asyncio.sleep(
                    self._redis_settings.stream_maintenance_error_backoff_seconds
                )

    async def _scan_and_requeue(self) -> None:
        """Paginate through all PEL entries idle beyond the stuck threshold."""
        cursor = "0-0"
        total_processed = 0

        while True:
            try:
                result = await self._redis.xautoclaim(
                    self._stream_key,
                    self._consumer_group,
                    STREAM_MAINTENANCE_CONSUMER_NAME,
                    self._redis_settings.stuck_timeout_ms,
                    cursor,
                    count=self._redis_settings.pel_xautoclaim_count,
                )
            except ResponseError as error:
                if is_missing_stream_or_group_error(error):
                    await self._recover_missing_stream()
                    return
                raise

            if not result:
                break

            next_cursor: str = result[0]
            messages: list[tuple[str, dict[str, str] | None]] = (
                result[1] if len(result) > 1 else []
            )
            deleted_ids: list[str] = result[2] if len(result) > 2 else []

            if deleted_ids:
                logger.info(
                    "PEL entries removed from stream during XAUTOCLAIM",
                    message_ids=deleted_ids,
                    count=len(deleted_ids),
                    stream_key=self._stream_key,
                )

            for message_id, fields in messages:
                if fields is None:
                    logger.info(
                        "Acknowledging tombstoned PEL message missing stream entry",
                        message_id=message_id,
                        stream_key=self._stream_key,
                    )
                    await ack_and_finalize_stream_entry(
                        self._redis,
                        stream_key=self._stream_key,
                        consumer_group=self._consumer_group,
                        message_id=message_id,
                    )
                    continue

                try:
                    await self._handle_stuck_message(message_id, fields)
                    total_processed += 1
                except Exception as error:
                    logger.exception(
                        "Failed to handle stuck PEL message, skipping",
                        message_id=message_id,
                        stream_key=self._stream_key,
                        error=str(error),
                    )

            if next_cursor == "0-0":
                break

            cursor = next_cursor

        if total_processed > 0:
            logger.info(
                "PEL requeue scan complete",
                total_processed=total_processed,
                stream_key=self._stream_key,
            )

    async def _cleanup_idle_consumers(self) -> None:
        try:
            await cleanup_idle_consumers_from_group(
                self._redis,
                stream_key=self._stream_key,
                consumer_group=self._consumer_group,
                idle_threshold_ms=self._redis_settings.consumer_cleanup_idle_ms,
                protected_consumer_names=self._protected_consumer_names,
            )
        except ResponseError as error:
            if not is_missing_stream_or_group_error(error):
                raise
            await self._recover_missing_stream()

    async def _handle_stuck_message(
        self, message_id: str, fields: dict[str, str]
    ) -> None:
        requeue_count = int(fields.get("requeue_count", "0"))
        max_requeue_count = self._redis_settings.pel_max_requeue_count

        if requeue_count >= max_requeue_count:
            logger.warning(
                "Discarding stuck message: requeue_count exceeded threshold",
                message_id=message_id,
                requeue_count=requeue_count,
                max_requeue_count=max_requeue_count,
                stream_key=self._stream_key,
            )
            await ack_and_finalize_stream_entry(
                self._redis,
                stream_key=self._stream_key,
                consumer_group=self._consumer_group,
                message_id=message_id,
            )
            return

        new_fields = dict(fields)
        new_fields["requeue_count"] = str(requeue_count + 1)

        try:
            await requeue_stream_entry(
                self._redis,
                stream_key=self._stream_key,
                consumer_group=self._consumer_group,
                message_id=message_id,
                fields=new_fields,
            )
        except ResponseError as error:
            if is_missing_stream_or_group_error(error):
                await self._recover_missing_stream()
                return
            raise

        logger.info(
            "Requeued stuck PEL message",
            original_message_id=message_id,
            new_requeue_count=requeue_count + 1,
            stream_key=self._stream_key,
        )
