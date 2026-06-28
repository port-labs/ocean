"""Redis-based leader election using ``SET … NX PX`` with TTL heartbeat."""

import asyncio

from loguru import logger
from redis.asyncio import Redis


class RedisLeaderElection:
    """Coordinate single-leader background work across pods via a Redis lock key."""

    def __init__(
        self,
        redis: Redis,
        leader_key: str,
        pod_id: str,
        *,
        name: str = "leader election",
        ttl_ms: int = 30_000,
        heartbeat_seconds: float = 10.0,
    ) -> None:
        self._redis = redis
        self._leader_key = leader_key
        self._pod_id = pod_id
        self._name = name
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
                f"{self._name} leader elected",
                leader_key=self._leader_key,
                pod_id=self._pod_id,
            )
        return bool(result)

    async def release(self) -> None:
        """Give up leadership and delete the lock key (best-effort)."""
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
                    f"{self._name} leader released lock",
                    leader_key=self._leader_key,
                )
        except Exception as error:
            logger.warning(
                f"Error releasing {self._name} leader lock",
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
                        f"{self._name} leader heartbeat renewed",
                        leader_key=self._leader_key,
                    )
                else:
                    logger.warning(
                        f"{self._name} leader lock lost — another pod took over",
                        leader_key=self._leader_key,
                    )
                    self._is_leader = False
                    break
            except asyncio.CancelledError:
                break
            except Exception as error:
                logger.warning(
                    f"{self._name} leader heartbeat error",
                    leader_key=self._leader_key,
                    error=str(error),
                )
