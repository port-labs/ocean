"""Tests for RedisStreamMaintenanceWorker."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest
from redis.exceptions import ResponseError

from port_ocean.config.settings import LiveEventsRedisSettings
from port_ocean.consumers.redis_stream_utils import (
    ACK_AND_FINALIZE_STREAM_ENTRY_SCRIPT,
    REQUEUE_STREAM_ENTRY_SCRIPT,
)
from port_ocean.consumers.stream_maintenance import RedisStreamMaintenanceWorker
from port_ocean.consumers.stream_maintenance.settings import (
    STREAM_MAINTENANCE_CONSUMER_NAME,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STREAM_KEY = "test/live-events/raw/event-stream"
_CONSUMER_GROUP = "test.integration"

_DEFAULT_REDIS_SETTINGS = LiveEventsRedisSettings(
    url="redis://localhost:6379",
    pel_stuck_timeout_seconds=60,
    pel_max_requeue_count=3,
    stream_maintenance_scan_interval_seconds=30.0,
    pel_xautoclaim_count=100,
    stream_maintenance_error_backoff_seconds=5.0,
)


def _make_redis() -> AsyncMock:
    redis = AsyncMock()
    redis.xautoclaim = AsyncMock(return_value=("0-0", [], []))
    redis.xinfo_consumers = AsyncMock(return_value=[])
    redis.eval = AsyncMock(return_value="1700000000001-0")
    redis.expire = AsyncMock(return_value=True)
    return redis


def _fields_from_requeue_eval_call(eval_call: Any) -> dict[str, str]:
    field_pairs = eval_call.args[5:]
    return dict(zip(field_pairs[0::2], field_pairs[1::2], strict=True))


def _make_worker(
    redis: AsyncMock,
    stream_key: str = _STREAM_KEY,
    consumer_group: str = _CONSUMER_GROUP,
    stream_consumer_name: str | None = None,
    **settings_overrides: Any,
) -> RedisStreamMaintenanceWorker:
    redis_settings = _DEFAULT_REDIS_SETTINGS.copy(update=settings_overrides)
    return RedisStreamMaintenanceWorker(
        redis,
        redis_settings=redis_settings,
        stream_key=stream_key,
        consumer_group=consumer_group,
        stream_consumer_name=stream_consumer_name,
    )


# ---------------------------------------------------------------------------
# RedisStreamMaintenanceWorker — _handle_stuck_message
# ---------------------------------------------------------------------------


class TestPELHandleStuckMessage:
    @pytest.mark.asyncio
    async def test_requeues_message_below_threshold(self) -> None:
        redis = _make_redis()
        worker = _make_worker(redis, pel_max_requeue_count=3)

        fields = {
            "webhookPath": "/webhook",
            "payload": '{"action":"push"}',
            "headers": "{}",
            "requeue_count": "1",
        }
        await worker._handle_stuck_message("1700000000000-0", fields)

        redis.eval.assert_awaited_once()
        eval_call = redis.eval.await_args
        assert eval_call is not None
        assert eval_call.args[0] == REQUEUE_STREAM_ENTRY_SCRIPT
        assert eval_call.args[2] == worker._stream_key
        assert eval_call.args[3] == worker._consumer_group
        assert eval_call.args[4] == "1700000000000-0"
        sent_fields = _fields_from_requeue_eval_call(eval_call)
        assert sent_fields["requeue_count"] == "2"
        assert sent_fields["webhookPath"] == "/webhook"

    @pytest.mark.asyncio
    async def test_requeue_uses_lua_script(self) -> None:
        redis = _make_redis()
        worker = _make_worker(redis, pel_max_requeue_count=3)

        fields = {"webhookPath": "/webhook", "payload": "{}", "headers": "{}"}
        await worker._handle_stuck_message("1700000000000-0", fields)

        redis.eval.assert_awaited_once()
        eval_call = redis.eval.await_args
        assert eval_call is not None
        assert eval_call.args[0] == REQUEUE_STREAM_ENTRY_SCRIPT
        assert eval_call.args[2] == worker._stream_key
        assert eval_call.args[3] == worker._consumer_group
        assert eval_call.args[4] == "1700000000000-0"
        sent_fields = _fields_from_requeue_eval_call(eval_call)
        assert sent_fields["requeue_count"] == "1"
        assert sent_fields["webhookPath"] == "/webhook"

    @pytest.mark.asyncio
    async def test_increments_requeue_count_from_zero(self) -> None:
        redis = _make_redis()
        worker = _make_worker(redis, pel_max_requeue_count=3)

        fields = {"webhookPath": "/webhook", "payload": "{}", "headers": "{}"}
        await worker._handle_stuck_message("1700000000000-0", fields)

        eval_call = redis.eval.await_args
        assert eval_call is not None
        sent_fields = _fields_from_requeue_eval_call(eval_call)
        assert sent_fields["requeue_count"] == "1"

    @pytest.mark.asyncio
    async def test_discards_message_at_threshold(self) -> None:
        redis = _make_redis()
        worker = _make_worker(redis, pel_max_requeue_count=3)

        fields = {
            "webhookPath": "/webhook",
            "payload": "{}",
            "headers": "{}",
            "requeue_count": "3",
        }
        await worker._handle_stuck_message("1700000000000-0", fields)

        redis.xadd.assert_not_awaited()
        redis.eval.assert_awaited_once_with(
            ACK_AND_FINALIZE_STREAM_ENTRY_SCRIPT,
            1,
            worker._stream_key,
            worker._consumer_group,
            "1700000000000-0",
        )

    @pytest.mark.asyncio
    async def test_discards_message_above_threshold(self) -> None:
        redis = _make_redis()
        worker = _make_worker(redis, pel_max_requeue_count=3)

        fields = {"requeue_count": "10"}
        await worker._handle_stuck_message("1700000000000-0", fields)

        redis.xadd.assert_not_awaited()
        redis.eval.assert_awaited_once()


# ---------------------------------------------------------------------------
# RedisStreamMaintenanceWorker — _scan_and_requeue
# ---------------------------------------------------------------------------


class TestPELScanAndRequeue:
    @pytest.mark.asyncio
    async def test_calls_xautoclaim_with_correct_args(self) -> None:
        redis = _make_redis()
        redis.xautoclaim = AsyncMock(return_value=("0-0", [], []))
        worker = _make_worker(
            redis, pel_stuck_timeout_seconds=60, pel_xautoclaim_count=100
        )

        await worker._scan_and_requeue()

        redis.xautoclaim.assert_awaited_once_with(
            worker._stream_key,
            worker._consumer_group,
            STREAM_MAINTENANCE_CONSUMER_NAME,
            60_000,
            "0-0",
            count=100,
        )

    @pytest.mark.asyncio
    async def test_uses_configured_xautoclaim_count(self) -> None:
        redis = _make_redis()
        redis.xautoclaim = AsyncMock(return_value=("0-0", [], []))
        worker = _make_worker(redis, pel_xautoclaim_count=25)

        await worker._scan_and_requeue()

        assert redis.xautoclaim.await_args is not None
        assert redis.xautoclaim.await_args.kwargs["count"] == 25

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

        assert redis.eval.await_count == 2

    @pytest.mark.asyncio
    async def test_paginates_through_non_zero_cursor_with_empty_batch(self) -> None:
        """XAUTOCLAIM can return an empty batch with a non-zero cursor when no
        entries in the current page are idle long enough; scanning must continue."""
        redis = _make_redis()
        page2_messages = [
            (
                "1700000000002-0",
                {"webhookPath": "/w", "payload": "{}", "headers": "{}"},
            ),
        ]
        cursors_used: list[str] = []

        async def fake_xautoclaim(stream, group, consumer, idle, cursor, count):  # type: ignore[no-untyped-def]
            cursors_used.append(cursor)
            if cursor == "0-0":
                return ("1700000000002-0", [], [])
            return ("0-0", page2_messages, [])

        redis.xautoclaim = fake_xautoclaim

        worker = _make_worker(redis)
        await worker._scan_and_requeue()

        assert cursors_used == ["0-0", "1700000000002-0"]
        redis.eval.assert_awaited_once()
        eval_call = redis.eval.await_args
        assert eval_call is not None
        assert eval_call.args[0] == REQUEUE_STREAM_ENTRY_SCRIPT
        assert eval_call.args[4] == "1700000000002-0"
        sent_fields = _fields_from_requeue_eval_call(eval_call)
        assert sent_fields["requeue_count"] == "1"

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

        redis.xautoclaim = fake_xautoclaim

        worker = _make_worker(redis)
        await worker._scan_and_requeue()

        assert call_count == 2
        assert redis.eval.await_count == 2

    @pytest.mark.asyncio
    async def test_no_eval_when_no_stuck_messages(self) -> None:
        redis = _make_redis()
        redis.xautoclaim = AsyncMock(return_value=("0-0", [], []))

        worker = _make_worker(redis)
        await worker._scan_and_requeue()

        redis.eval.assert_not_awaited()

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

        redis.eval.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handles_deleted_ids_without_eval_or_requeue(self) -> None:
        """Redis 7.0+ returns ghost PEL entries in the third response element."""
        redis = _make_redis()
        redis.xautoclaim = AsyncMock(
            return_value=("0-0", [], ["1700000000999-0", "1700000000998-0"])
        )

        worker = _make_worker(redis)
        await worker._scan_and_requeue()

        redis.eval.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_acknowledges_tombstoned_message_with_none_fields(self) -> None:
        """Redis 6.x can return nil fields for deleted stream entries in result[1]."""
        redis = _make_redis()
        messages = [
            ("1700000000999-0", None),
            (
                "1700000000001-0",
                {"webhookPath": "/w", "payload": "{}", "headers": "{}"},
            ),
        ]
        redis.xautoclaim = AsyncMock(return_value=("0-0", messages, []))

        worker = _make_worker(redis)
        await worker._scan_and_requeue()

        assert redis.eval.await_count == 2
        assert (
            redis.eval.await_args_list[0].args[0]
            == ACK_AND_FINALIZE_STREAM_ENTRY_SCRIPT
        )
        assert redis.eval.await_args_list[1].args[0] == REQUEUE_STREAM_ENTRY_SCRIPT

    @pytest.mark.asyncio
    async def test_continues_scan_when_one_message_fails(self) -> None:
        redis = _make_redis()
        messages = [
            (
                "1700000000001-0",
                {"requeue_count": "not-a-number"},
            ),
            (
                "1700000000002-0",
                {"webhookPath": "/w", "payload": "{}", "headers": "{}"},
            ),
        ]
        redis.xautoclaim = AsyncMock(return_value=("0-0", messages, []))

        worker = _make_worker(redis)
        await worker._scan_and_requeue()

        redis.eval.assert_awaited_once()
        eval_call = redis.eval.await_args
        assert eval_call is not None
        sent_fields = _fields_from_requeue_eval_call(eval_call)
        assert sent_fields["requeue_count"] == "1"
        assert eval_call.args[4] == "1700000000002-0"


# ---------------------------------------------------------------------------
# RedisStreamMaintenanceWorker — worker loop
# ---------------------------------------------------------------------------


class TestStreamMaintenanceWorkerLoop:
    @pytest.mark.asyncio
    async def test_worker_stops_cleanly(self) -> None:
        redis = _make_redis()
        scan_calls: list[int] = []

        async def fake_scan() -> None:
            scan_calls.append(1)

        worker = _make_worker(redis, stream_maintenance_scan_interval_seconds=0.05)
        worker._scan_and_requeue = fake_scan  # type: ignore[method-assign]
        await worker.start()
        await asyncio.sleep(0.25)
        await worker.stop()

        assert len(scan_calls) >= 1
        assert worker._is_running is False
        assert worker._lifecycle_task is None

    @pytest.mark.asyncio
    async def test_all_pods_scan_independently(self) -> None:
        """Multiple workers sharing the same Redis instance should each scan."""
        redis = _make_redis()
        scan_counts: dict[str, int] = {"a": 0, "b": 0}

        worker_a = _make_worker(redis, stream_maintenance_scan_interval_seconds=0.05)
        worker_b = _make_worker(redis, stream_maintenance_scan_interval_seconds=0.05)

        async def fake_scan_a() -> None:
            scan_counts["a"] += 1

        async def fake_scan_b() -> None:
            scan_counts["b"] += 1

        worker_a._scan_and_requeue = fake_scan_a  # type: ignore[method-assign]
        worker_b._scan_and_requeue = fake_scan_b  # type: ignore[method-assign]

        await worker_a.start()
        await worker_b.start()
        await asyncio.sleep(0.25)
        await worker_a.stop()
        await worker_b.stop()

        assert scan_counts["a"] >= 1
        assert scan_counts["b"] >= 1

    @pytest.mark.asyncio
    async def test_worker_loop_backoffs_after_unexpected_error(self) -> None:
        redis = _make_redis()
        scan_calls: list[int] = []

        async def failing_scan() -> None:
            scan_calls.append(1)
            raise RuntimeError("redis unavailable")

        worker = _make_worker(
            redis,
            stream_maintenance_scan_interval_seconds=0.01,
            stream_maintenance_error_backoff_seconds=0.05,
        )
        worker._scan_and_requeue = failing_scan  # type: ignore[method-assign]
        await worker.start()

        await asyncio.sleep(0.2)
        await worker.stop()

        assert len(scan_calls) >= 2, "Expected retries after error backoff"


class TestStreamMaintenanceIdleConsumerCleanup:
    @pytest.mark.asyncio
    async def test_cleanup_removes_idle_consumers_after_scan(self) -> None:
        redis = _make_redis()
        redis.xinfo_consumers = AsyncMock(
            return_value=[
                {
                    "name": "integration-dead-pod",
                    "pending": 0,
                    "idle": 5_000_000,
                }
            ]
        )
        redis.xgroup_delconsumer = AsyncMock(return_value=0)

        worker = _make_worker(
            redis,
            stream_consumer_name="integration-live-pod",
            stream_maintenance_consumer_cleanup_idle_seconds=60,
        )
        await worker._cleanup_idle_consumers()

        redis.xgroup_delconsumer.assert_awaited_once_with(
            _STREAM_KEY,
            _CONSUMER_GROUP,
            "integration-dead-pod",
        )

    @pytest.mark.asyncio
    async def test_cleanup_skips_protected_stream_consumer_name(self) -> None:
        redis = _make_redis()
        redis.xinfo_consumers = AsyncMock(
            return_value=[
                {
                    "name": "integration-live-pod",
                    "pending": 0,
                    "idle": 5_000_000,
                },
                {
                    "name": STREAM_MAINTENANCE_CONSUMER_NAME,
                    "pending": 0,
                    "idle": 5_000_000,
                },
            ]
        )
        redis.xgroup_delconsumer = AsyncMock(return_value=0)

        worker = _make_worker(
            redis,
            stream_consumer_name="integration-live-pod",
            stream_maintenance_consumer_cleanup_idle_seconds=60,
        )
        await worker._cleanup_idle_consumers()

        redis.xgroup_delconsumer.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_worker_loop_skips_cleanup_when_disabled(self) -> None:
        redis = _make_redis()
        cleanup_calls: list[int] = []

        async def fake_scan() -> None:
            return None

        async def fake_cleanup() -> None:
            cleanup_calls.append(1)

        worker = _make_worker(
            redis,
            stream_maintenance_scan_interval_seconds=0.05,
            stream_maintenance_consumer_cleanup_enabled=False,
        )
        worker._scan_and_requeue = fake_scan  # type: ignore[method-assign]
        worker._cleanup_idle_consumers = fake_cleanup  # type: ignore[method-assign]

        await worker.start()
        await asyncio.sleep(0.15)
        await worker.stop()

        assert cleanup_calls == []


class TestStreamMaintenanceRecoverMissingStream:
    @pytest.mark.asyncio
    async def test_scan_recovers_when_xautoclaim_raises_nogroup(self) -> None:
        redis = _make_redis()
        redis.xautoclaim = AsyncMock(
            side_effect=ResponseError(
                "NOGROUP No such key 'stream' or consumer group 'test.integration'"
            )
        )
        redis.exists = AsyncMock(return_value=0)
        redis.xgroup_create = AsyncMock()
        redis.expire = AsyncMock()

        worker = _make_worker(redis)
        await worker._scan_and_requeue()

        redis.xgroup_create.assert_awaited_once()
        redis.xadd.assert_not_awaited()
        redis.eval.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_requeue_recovers_when_eval_raises_nogroup(self) -> None:
        redis = _make_redis()
        redis.exists = AsyncMock(return_value=0)
        redis.xgroup_create = AsyncMock()
        redis.expire = AsyncMock()
        redis.eval = AsyncMock(
            side_effect=ResponseError("NOGROUP No such key 'stream' or consumer group")
        )

        worker = _make_worker(redis, pel_max_requeue_count=3)
        fields = {"webhookPath": "/webhook", "payload": "{}", "headers": "{}"}
        await worker._handle_stuck_message("1700000000000-0", fields)

        redis.xgroup_create.assert_awaited_once()
        redis.eval.assert_awaited_once()
