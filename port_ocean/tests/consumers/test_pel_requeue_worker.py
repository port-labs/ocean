"""Tests for PELRequeueWorker and RedisLeaderElection."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from port_ocean.consumers.pel_requeue_worker import (
    PELRequeueWorker,
    RedisLeaderElection,
    _LEADER_KEY_SUFFIX,
    _PEL_CONSUMER_NAME,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_redis() -> AsyncMock:
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True)
    redis.get = AsyncMock(return_value=None)
    redis.pexpire = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.xautoclaim = AsyncMock(return_value=("0-0", [], []))
    redis.xadd = AsyncMock(return_value="1700000000001-0")
    redis.xack = AsyncMock(return_value=1)
    return redis


def _make_worker(redis: AsyncMock, **overrides) -> PELRequeueWorker:
    defaults = dict(
        redis=redis,
        stream_key="test/live-events/raw/event-stream",
        consumer_group="test.integration",
        pod_id="pod-abc",
        stuck_timeout_ms=60_000,
        max_requeue_count=3,
        scan_interval_seconds=30.0,
        leader_ttl_ms=30_000,
        leader_heartbeat_seconds=10.0,
        election_retry_seconds=0.05,
    )
    defaults.update(overrides)
    return PELRequeueWorker(**defaults)


# ---------------------------------------------------------------------------
# RedisLeaderElection
# ---------------------------------------------------------------------------


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

        redis.pexpire = fake_pexpire  # type: ignore[assignment]

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
        # Simulate another pod took over
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


# ---------------------------------------------------------------------------
# PELRequeueWorker — leader election integration
# ---------------------------------------------------------------------------


class TestPELRequeueWorkerLeaderElection:
    @pytest.mark.asyncio
    async def test_lifecycle_task_always_starts(self) -> None:
        """Every pod starts the lifecycle loop regardless of election outcome."""
        redis = _make_redis()
        redis.set = AsyncMock(return_value=True)  # wins election

        worker = _make_worker(redis)
        await worker.start()

        assert worker._is_running is True
        assert worker._lifecycle_task is not None
        await worker.stop()

    @pytest.mark.asyncio
    async def test_lifecycle_task_starts_even_when_not_leader(self) -> None:
        """Non-leader pods must keep the lifecycle task alive to retry later."""
        redis = _make_redis()
        redis.set = AsyncMock(return_value=None)  # loses election

        worker = _make_worker(redis, scan_interval_seconds=999.0)
        await worker.start()

        assert worker._is_running is True
        assert worker._lifecycle_task is not None
        await worker.stop()

    @pytest.mark.asyncio
    async def test_leader_key_uses_stream_key_prefix(self) -> None:
        redis = _make_redis()
        stream_key = "uuid123/live-events/raw/event-stream"
        worker = _make_worker(redis, stream_key=stream_key)
        await worker.start()
        await asyncio.sleep(0.05)

        expected_key = f"{stream_key}:{_LEADER_KEY_SUFFIX}"
        first_call = redis.set.await_args_list[0]
        assert first_call.args[0] == expected_key
        assert first_call.args[1] == "pod-abc"
        await worker.stop()

    @pytest.mark.asyncio
    async def test_stop_releases_leader_lock(self) -> None:
        redis = _make_redis()
        redis.get = AsyncMock(return_value="pod-abc")

        worker = _make_worker(redis)
        await worker.start()
        await worker.stop()

        redis.delete.assert_awaited()

    @pytest.mark.asyncio
    async def test_follower_retries_election_after_leader_dies(self) -> None:
        """Simulate leader dying: SET first returns None (locked), then True (expired)."""
        redis = _make_redis()
        call_count = 0

        async def flipping_set(*args: object, **kwargs: object) -> object:
            nonlocal call_count
            call_count += 1
            return None if call_count == 1 else True

        redis.set = flipping_set  # type: ignore[assignment]
        redis.get = AsyncMock(return_value="pod-abc")

        scanned: list[bool] = []

        worker = _make_worker(
            redis, election_retry_seconds=0.05, scan_interval_seconds=999.0
        )
        worker._scan_and_requeue = AsyncMock(  # type: ignore[method-assign]
            side_effect=lambda: scanned.append(True)
        )
        await worker.start()

        # Allow: first attempt (loses) → sleep 0.05s → second attempt (wins) → scan
        await asyncio.sleep(0.3)
        await worker.stop()

        assert call_count >= 2, "Expected at least two election attempts"
        assert len(scanned) >= 1, "Expected at least one scan after winning election"


# ---------------------------------------------------------------------------
# PELRequeueWorker — _handle_stuck_message
# ---------------------------------------------------------------------------


class TestPELHandleStuckMessage:
    @pytest.mark.asyncio
    async def test_requeues_message_below_threshold(self) -> None:
        redis = _make_redis()
        worker = _make_worker(redis, max_requeue_count=3)

        fields = {
            "webhookPath": "/webhook",
            "payload": '{"action":"push"}',
            "headers": "{}",
            "requeue_count": "1",
        }
        await worker._handle_stuck_message("1700000000000-0", fields)

        redis.xadd.assert_awaited_once()
        call_args = redis.xadd.await_args
        sent_fields: dict = call_args.args[1]
        assert sent_fields["requeue_count"] == "2"
        assert sent_fields["webhookPath"] == "/webhook"

        redis.xack.assert_awaited_once_with(
            worker._stream_key, worker._consumer_group, "1700000000000-0"
        )

    @pytest.mark.asyncio
    async def test_increments_requeue_count_from_zero(self) -> None:
        redis = _make_redis()
        worker = _make_worker(redis, max_requeue_count=3)

        fields = {"webhookPath": "/webhook", "payload": "{}", "headers": "{}"}
        await worker._handle_stuck_message("1700000000000-0", fields)

        sent_fields: dict = redis.xadd.await_args.args[1]
        assert sent_fields["requeue_count"] == "1"

    @pytest.mark.asyncio
    async def test_discards_message_at_threshold(self) -> None:
        redis = _make_redis()
        worker = _make_worker(redis, max_requeue_count=3)

        fields = {
            "webhookPath": "/webhook",
            "payload": "{}",
            "headers": "{}",
            "requeue_count": "3",
        }
        await worker._handle_stuck_message("1700000000000-0", fields)

        redis.xadd.assert_not_awaited()
        redis.xack.assert_awaited_once_with(
            worker._stream_key, worker._consumer_group, "1700000000000-0"
        )

    @pytest.mark.asyncio
    async def test_discards_message_above_threshold(self) -> None:
        redis = _make_redis()
        worker = _make_worker(redis, max_requeue_count=3)

        fields = {"requeue_count": "10"}
        await worker._handle_stuck_message("1700000000000-0", fields)

        redis.xadd.assert_not_awaited()
        redis.xack.assert_awaited_once()


# ---------------------------------------------------------------------------
# PELRequeueWorker — _scan_and_requeue
# ---------------------------------------------------------------------------


class TestPELScanAndRequeue:
    @pytest.mark.asyncio
    async def test_calls_xautoclaim_with_correct_args(self) -> None:
        redis = _make_redis()
        redis.xautoclaim = AsyncMock(return_value=("0-0", [], []))
        worker = _make_worker(redis, stuck_timeout_ms=60_000)

        await worker._scan_and_requeue()

        redis.xautoclaim.assert_awaited_once_with(
            worker._stream_key,
            worker._consumer_group,
            _PEL_CONSUMER_NAME,
            60_000,
            "0-0",
            count=100,
        )

    @pytest.mark.asyncio
    async def test_processes_multiple_stuck_messages(self) -> None:
        redis = _make_redis()
        messages = [
            (
                "1700000000001-0",
                {"webhookPath": "/w", "payload": "{}", "headers": "{}"},
            ),
            (
                "1700000000002-0",
                {"webhookPath": "/w", "payload": "{}", "headers": "{}"},
            ),
        ]
        redis.xautoclaim = AsyncMock(return_value=("0-0", messages, []))

        worker = _make_worker(redis)
        await worker._scan_and_requeue()

        assert redis.xadd.await_count == 2
        assert redis.xack.await_count == 2

    @pytest.mark.asyncio
    async def test_paginates_when_next_cursor_is_not_zero(self) -> None:
        redis = _make_redis()
        page1_messages = [
            (
                "1700000000001-0",
                {"webhookPath": "/w", "payload": "{}", "headers": "{}"},
            ),
        ]
        page2_messages = [
            (
                "1700000000002-0",
                {"webhookPath": "/w", "payload": "{}", "headers": "{}"},
            ),
        ]

        call_count = 0

        async def fake_xautoclaim(stream, group, consumer, idle, cursor, count):  # type: ignore[no-untyped-def]
            nonlocal call_count
            call_count += 1
            if cursor == "0-0":
                return ("1700000000002-0", page1_messages, [])
            return ("0-0", page2_messages, [])

        redis.xautoclaim = fake_xautoclaim  # type: ignore[assignment]

        worker = _make_worker(redis)
        await worker._scan_and_requeue()

        assert call_count == 2
        assert redis.xadd.await_count == 2

    @pytest.mark.asyncio
    async def test_no_xadd_when_no_stuck_messages(self) -> None:
        redis = _make_redis()
        redis.xautoclaim = AsyncMock(return_value=("0-0", [], []))

        worker = _make_worker(redis)
        await worker._scan_and_requeue()

        redis.xadd.assert_not_awaited()
        redis.xack.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_handles_two_element_xautoclaim_response(self) -> None:
        """Older Redis versions return (next_id, messages) without deleted_ids."""
        redis = _make_redis()
        messages = [
            (
                "1700000000001-0",
                {"webhookPath": "/w", "payload": "{}", "headers": "{}"},
            ),
        ]
        redis.xautoclaim = AsyncMock(return_value=("0-0", messages))

        worker = _make_worker(redis)
        await worker._scan_and_requeue()

        redis.xadd.assert_awaited_once()


# ---------------------------------------------------------------------------
# PELRequeueWorker — worker_loop stop behaviour
# ---------------------------------------------------------------------------


class TestPELWorkerLoop:
    @pytest.mark.asyncio
    async def test_worker_stops_cleanly(self) -> None:
        redis = _make_redis()
        scan_calls: list[int] = []

        async def fake_scan() -> None:
            scan_calls.append(1)

        worker = _make_worker(redis, scan_interval_seconds=0.05)
        worker._scan_and_requeue = fake_scan  # type: ignore[method-assign]
        await worker.start()
        await asyncio.sleep(0.25)
        await worker.stop()

        assert len(scan_calls) >= 1
        assert worker._is_running is False
        assert worker._lifecycle_task is None
