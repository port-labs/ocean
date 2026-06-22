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

from loguru import logger
from redis.asyncio import Redis

_LEADER_KEY_SUFFIX = "pel-requeue:leader"
_PEL_CONSUMER_NAME = "pel-requeue-worker"


class RedisLeaderElection:
    """Redis-based leader election using ``SET … NX PX``."""

    def __init__(
        self,
        redis: Redis,
        leader_key: str,
        pod_id: str,
        ttl_ms: int = 30_000,
        heartbeat_seconds: float = 10.0,
    ) -> None:
        self._redis = redis
        self._leader_key = leader_key
        self._pod_id = pod_id
        self._ttl_ms = ttl_ms
        self._heartbeat_seconds = heartbeat_seconds
        self._is_leader = False
        self._heartbeat_task: asyncio.Task[None] | None = None

    @property
    def is_leader(self) -> bool:
        return self._is_leader

    async def try_acquire(self) -> bool:
        """Attempt to become leader atomically.

        Returns ``True`` when this pod wins and the heartbeat loop has been
        started, ``False`` when another pod already holds the lock.
        """
        result = await self._redis.set(
            self._leader_key, self._pod_id, nx=True, px=self._ttl_ms
        )
        if result:
            self._is_leader = True
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            logger.info(
                "PEL requeue leader elected",
                leader_key=self._leader_key,
                pod_id=self._pod_id,
            )
        return bool(result)

    async def release(self) -> None:
        """Relinquish leadership and delete the lock key (best-effort)."""
        self._is_leader = False
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            await asyncio.gather(self._heartbeat_task, return_exceptions=True)
            self._heartbeat_task = None
        try:
            current = await self._redis.get(self._leader_key)
            if current == self._pod_id:
                await self._redis.delete(self._leader_key)
                logger.info(
                    "PEL requeue leader released lock", leader_key=self._leader_key
                )
        except Exception as error:
            logger.warning(
                "Error releasing PEL requeue leader lock",
                leader_key=self._leader_key,
                error=str(error),
            )

    async def _heartbeat_loop(self) -> None:
        """Renew the leader TTL every ``heartbeat_seconds`` seconds."""
        while self._is_leader:
            try:
                await asyncio.sleep(self._heartbeat_seconds)
                current = await self._redis.get(self._leader_key)
                if current == self._pod_id:
                    await self._redis.pexpire(self._leader_key, self._ttl_ms)
                    logger.debug(
                        "PEL requeue leader heartbeat renewed",
                        leader_key=self._leader_key,
                    )
                else:
                    logger.warning(
                        "PEL requeue leader lock lost — another pod took over",
                        leader_key=self._leader_key,
                    )
                    self._is_leader = False
                    break
            except asyncio.CancelledError:
                break
            except Exception as error:
                logger.warning(
                    "PEL requeue leader heartbeat error",
                    leader_key=self._leader_key,
                    error=str(error),
                )


class PELRequeueWorker:
    """Background worker that rescues messages stuck in the Redis PEL.

    Uses :class:`RedisLeaderElection` so that only one pod runs the scan at
    any given time.  The worker loop:

    - Calls ``XAUTOCLAIM`` to find and claim entries idle longer than
      ``stuck_timeout_ms``.
    - Re-enqueues them via ``XADD`` with an incremented ``requeue_count``
      field, then ``XACK``s the original entry to clear it from the PEL.
    - Discards (ACKs without re-enqueuing) messages whose ``requeue_count``
      has reached ``max_requeue_count``.
    """

    def __init__(
        self,
        redis: Redis,
        stream_key: str,
        consumer_group: str,
        pod_id: str,
        stuck_timeout_ms: int = 60_000,
        max_requeue_count: int = 3,
        scan_interval_seconds: float = 30.0,
        leader_ttl_ms: int = 30_000,
        leader_heartbeat_seconds: float = 10.0,
    ) -> None:
        self._redis = redis
        self._stream_key = stream_key
        self._consumer_group = consumer_group
        self._stuck_timeout_ms = stuck_timeout_ms
        self._max_requeue_count = max_requeue_count
        self._scan_interval_seconds = scan_interval_seconds
        self._is_running = False
        self._worker_task: asyncio.Task[None] | None = None
        self._leader_election = RedisLeaderElection(
            redis=redis,
            leader_key=f"{stream_key}:{_LEADER_KEY_SUFFIX}",
            pod_id=pod_id,
            ttl_ms=leader_ttl_ms,
            heartbeat_seconds=leader_heartbeat_seconds,
        )

    async def start(self) -> None:
        """Compete for leadership; if this pod wins, start the worker loop."""
        is_leader = await self._leader_election.try_acquire()
        if not is_leader:
            logger.info(
                "PEL requeue worker: not the leader, worker not started",
                stream_key=self._stream_key,
            )
            return

        self._is_running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info(
            "PEL requeue worker started",
            stream_key=self._stream_key,
            consumer_group=self._consumer_group,
        )

    async def stop(self) -> None:
        """Stop the worker loop and release the leader lock."""
        self._is_running = False
        if self._worker_task is not None:
            self._worker_task.cancel()
            await asyncio.gather(self._worker_task, return_exceptions=True)
            self._worker_task = None
        await self._leader_election.release()

    async def _worker_loop(self) -> None:
        while self._is_running:
            try:
                await self._scan_and_requeue()
            except asyncio.CancelledError:
                break
            except Exception as error:
                logger.exception(
                    "Unexpected error in PEL requeue worker scan",
                    error=str(error),
                )
            try:
                await asyncio.sleep(self._scan_interval_seconds)
            except asyncio.CancelledError:
                break

    async def _scan_and_requeue(self) -> None:
        """Paginate through all PEL entries idle beyond the stuck threshold."""
        cursor = "0-0"
        total_processed = 0

        while True:
            result = await self._redis.xautoclaim(
                self._stream_key,
                self._consumer_group,
                _PEL_CONSUMER_NAME,
                self._stuck_timeout_ms,
                cursor,
                count=100,
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

        if requeue_count >= self._max_requeue_count:
            logger.warning(
                "Discarding stuck message: requeue_count exceeded threshold",
                message_id=message_id,
                requeue_count=requeue_count,
                max_requeue_count=self._max_requeue_count,
                stream_key=self._stream_key,
            )
            await self._redis.xack(self._stream_key, self._consumer_group, message_id)
            return

        new_fields = dict(fields)
        new_fields["requeue_count"] = str(requeue_count + 1)

        await self._redis.xadd(self._stream_key, new_fields)
        await self._redis.xack(self._stream_key, self._consumer_group, message_id)

        logger.info(
            "Requeued stuck PEL message",
            original_message_id=message_id,
            new_requeue_count=requeue_count + 1,
            stream_key=self._stream_key,
        )
