"""Tests for RedisLeaderElection."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from port_ocean.consumers.pel_requeue.leader_election import RedisLeaderElection


def _make_redis() -> AsyncMock:
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True)
    redis.get = AsyncMock(return_value=None)
    redis.pexpire = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    return redis


class TestRedisLeaderElection:
    @pytest.mark.asyncio
    async def test_try_acquire_returns_true_when_set_succeeds(self) -> None:
        redis = _make_redis()
        redis.set = AsyncMock(return_value=True)

        election = RedisLeaderElection(
            redis=redis,
            leader_key="mykey",
            pod_id="pod-1",
            ttl_ms=30_000,
            heartbeat_seconds=10.0,
        )
        result = await election.try_acquire()

        assert result is True
        assert election.is_leader is True
        redis.set.assert_awaited_once_with("mykey", "pod-1", nx=True, px=30_000)

        await election.release()

    @pytest.mark.asyncio
    async def test_try_acquire_returns_false_when_set_fails(self) -> None:
        redis = _make_redis()
        redis.set = AsyncMock(return_value=None)

        election = RedisLeaderElection(
            redis=redis,
            leader_key="mykey",
            pod_id="pod-2",
            ttl_ms=30_000,
            heartbeat_seconds=10.0,
        )
        result = await election.try_acquire()

        assert result is False
        assert election.is_leader is False

    @pytest.mark.asyncio
    async def test_release_deletes_key_when_still_leader(self) -> None:
        redis = _make_redis()
        redis.get = AsyncMock(return_value="pod-1")

        election = RedisLeaderElection(
            redis=redis,
            leader_key="mykey",
            pod_id="pod-1",
            ttl_ms=30_000,
            heartbeat_seconds=10.0,
        )
        await election.try_acquire()
        await election.release()

        redis.delete.assert_awaited_once_with("mykey")
        assert election.is_leader is False

    @pytest.mark.asyncio
    async def test_release_does_not_delete_key_owned_by_another_pod(self) -> None:
        redis = _make_redis()
        redis.get = AsyncMock(return_value="other-pod")

        election = RedisLeaderElection(
            redis=redis,
            leader_key="mykey",
            pod_id="pod-1",
            ttl_ms=30_000,
            heartbeat_seconds=10.0,
        )
        await election.try_acquire()
        await election.release()

        redis.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_heartbeat_renews_ttl_while_leader(self) -> None:
        redis = _make_redis()
        redis.get = AsyncMock(return_value="pod-1")
        renewed: list[bool] = []

        async def fake_pexpire(key: str, ttl: int) -> bool:
            renewed.append(True)
            return True

        redis.pexpire = fake_pexpire

        election = RedisLeaderElection(
            redis=redis,
            leader_key="mykey",
            pod_id="pod-1",
            ttl_ms=30_000,
            heartbeat_seconds=0.05,
        )
        await election.try_acquire()
        await asyncio.sleep(0.15)
        await election.release()

        assert len(renewed) >= 1

    @pytest.mark.asyncio
    async def test_heartbeat_stops_when_lock_stolen(self) -> None:
        redis = _make_redis()
        redis.get = AsyncMock(return_value="other-pod")

        election = RedisLeaderElection(
            redis=redis,
            leader_key="mykey",
            pod_id="pod-1",
            ttl_ms=30_000,
            heartbeat_seconds=0.05,
        )
        await election.try_acquire()
        await asyncio.sleep(0.15)

        assert election.is_leader is False
