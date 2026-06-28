"""PEL (Pending Entry List) requeue worker with Redis-based leader election.

Only one pod runs the worker at any time. Leadership is coordinated via a
Redis key with a short TTL that the leader continuously renews. If the leader
dies the TTL expires and another pod wins the next election attempt.

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

from port_ocean.consumers.pel_requeue.leader_election import RedisLeaderElection
from port_ocean.consumers.pel_requeue.settings import (
    PELRequeueWorkerSettings,
    _PEL_CONSUMER_NAME,
    _PEL_LEADER_ELECTION_NAME,
)


class PELRequeueWorker:
    """Background worker that rescues messages stuck in the Redis PEL.

    Uses :class:`RedisLeaderElection` so that only one pod runs the scan at
    any given time. Every pod runs a continuous lifecycle loop that competes
    for leadership, scans the PEL while leader, and re-enters election when
    leadership is lost.

    The worker itself contains no processing logic — consumer pods handle all
    actual processing.
    """

    def __init__(self, redis: Redis, settings: PELRequeueWorkerSettings) -> None:
        self._redis = redis
        self._settings = settings
        self._is_running = False
        self._lifecycle_task: asyncio.Task[None] | None = None
        self._leader_election = RedisLeaderElection(
            redis=redis,
            leader_key=settings.leader_key,
            pod_id=settings.pod_id,
            name=_PEL_LEADER_ELECTION_NAME,
            ttl_ms=settings.leader_ttl_ms,
            heartbeat_seconds=settings.leader_heartbeat_seconds,
        )

    @property
    def _stream_key(self) -> str:
        return self._settings.stream_key

    @property
    def _consumer_group(self) -> str:
        return self._settings.consumer_group

    async def start(self) -> None:
        """Start the lifecycle loop on every pod.

        All pods compete continuously for leadership so that when the current
        leader dies a follower takes over automatically once the TTL expires.
        """
        self._is_running = True
        self._lifecycle_task = asyncio.create_task(self._lifecycle_loop())
        logger.info(
            "PEL requeue worker lifecycle started",
            stream_key=self._stream_key,
            consumer_group=self._consumer_group,
        )

    async def stop(self) -> None:
        """Stop the lifecycle loop and release the leader lock."""
        self._is_running = False
        if self._lifecycle_task is not None:
            self._lifecycle_task.cancel()
            await asyncio.gather(self._lifecycle_task, return_exceptions=True)
            self._lifecycle_task = None
        await self._leader_election.release()

    async def _lifecycle_loop(self) -> None:
        """Compete for leadership; scan the PEL when leader; re-enter election on loss."""
        while self._is_running:
            try:
                if not await self._ensure_leadership():
                    continue

                await self._run_leader_cycle()
            except asyncio.CancelledError:
                break
            except Exception as error:
                logger.exception(
                    "Unexpected error in PEL requeue lifecycle loop",
                    error=str(error),
                )
                await asyncio.sleep(self._settings.lifecycle_error_backoff_seconds)

    async def _ensure_leadership(self) -> bool:
        """Try to become leader; sleep and retry when another pod holds the lock."""
        if self._leader_election.is_leader:
            return True

        won = await self._leader_election.try_acquire()
        if won:
            logger.info(
                "PEL requeue worker became leader, starting scans",
                stream_key=self._stream_key,
            )
            return True

        logger.debug(
            "PEL requeue worker: not the leader, retrying after delay",
            stream_key=self._stream_key,
            retry_in_seconds=self._settings.election_retry_seconds,
        )
        await asyncio.sleep(self._settings.election_retry_seconds)
        return False

    async def _run_leader_cycle(self) -> None:
        """Run one PEL scan, wait for the next tick, and detect leadership loss."""
        await self._scan_and_requeue()
        await asyncio.sleep(self._settings.scan_interval_seconds)

        if not self._leader_election.is_leader:
            logger.info(
                "PEL requeue worker lost leadership, re-entering election",
                stream_key=self._stream_key,
            )

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
