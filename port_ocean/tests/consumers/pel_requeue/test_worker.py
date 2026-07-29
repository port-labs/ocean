"""Tests for PELRequeueWorker."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock

import pytest

from port_ocean.config.settings import LiveEventsRedisSettings
from port_ocean.consumers.pel_requeue import PELRequeueWorker
from port_ocean.consumers.pel_requeue.settings import PEL_CONSUMER_NAME

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STREAM_KEY = "test/live-events/raw/event-stream"
_CONSUMER_GROUP = "test.integration"

_DEFAULT_REDIS_SETTINGS = LiveEventsRedisSettings(
    url="redis://localhost:6379",
    pel_stuck_timeout_seconds=60,
    pel_max_requeue_count=3,
    pel_scan_interval_seconds=30.0,
    pel_xautoclaim_count=100,
    pel_lifecycle_error_backoff_seconds=5.0,
)


def _make_redis() -> AsyncMock:
    redis = AsyncMock()
    redis.xautoclaim = AsyncMock(return_value=("0-0", [], []))
    redis.xadd = AsyncMock(return_value="1700000000001-0")
    redis.xack = AsyncMock(return_value=1)

    @asynccontextmanager
    async def fake_pipeline(
        *_args: object, **_kwargs: object
    ) -> AsyncIterator[AsyncMock]:
        pipe = AsyncMock()
        pipe.xadd = redis.xadd
        pipe.xack = redis.xack
        pipe.execute = AsyncMock(return_value=["1700000000001-0", 1])
        yield pipe

    redis.pipeline = fake_pipeline
    return redis


def _make_worker(
    redis: AsyncMock,
    stream_key: str = _STREAM_KEY,
    consumer_group: str = _CONSUMER_GROUP,
    **settings_overrides: Any,
) -> PELRequeueWorker:
    redis_settings = _DEFAULT_REDIS_SETTINGS.copy(update=settings_overrides)
    return PELRequeueWorker(
        redis,
        redis_settings=redis_settings,
        stream_key=stream_key,
        consumer_group=consumer_group,
    )


# ---------------------------------------------------------------------------
# PELRequeueWorker — _handle_stuck_message
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

        redis.xadd.assert_awaited_once()
        call_args = redis.xadd.await_args
        sent_fields: dict[str, str] = call_args.args[1]
        assert sent_fields["requeue_count"] == "2"
        assert sent_fields["webhookPath"] == "/webhook"

        redis.xack.assert_awaited_once_with(
            worker._stream_key, worker._consumer_group, "1700000000000-0"
        )

    @pytest.mark.asyncio
    async def test_requeue_uses_transactional_pipeline(self) -> None:
        redis = _make_redis()
        worker = _make_worker(redis, pel_max_requeue_count=3)

        pipeline_calls: list[dict[str, Any]] = []

        @asynccontextmanager
        async def tracking_pipeline(
            *_args: object, **kwargs: object
        ) -> AsyncIterator[AsyncMock]:
            pipeline_calls.append(kwargs)
            pipe = AsyncMock()
            pipe.xadd = redis.xadd
            pipe.xack = redis.xack
            pipe.execute = AsyncMock(return_value=["1700000000001-0", 1])
            yield pipe

        redis.pipeline = tracking_pipeline

        fields = {"webhookPath": "/webhook", "payload": "{}", "headers": "{}"}
        await worker._handle_stuck_message("1700000000000-0", fields)

        assert pipeline_calls == [{"transaction": True}]
        redis.xadd.assert_awaited_once()
        redis.xack.assert_awaited_once()
        assert redis.xadd.await_args_list[0].args[0] == worker._stream_key

    @pytest.mark.asyncio
    async def test_increments_requeue_count_from_zero(self) -> None:
        redis = _make_redis()
        worker = _make_worker(redis, pel_max_requeue_count=3)

        fields = {"webhookPath": "/webhook", "payload": "{}", "headers": "{}"}
        await worker._handle_stuck_message("1700000000000-0", fields)

        sent_fields: dict[str, str] = redis.xadd.await_args.args[1]
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
        redis.xack.assert_awaited_once_with(
            worker._stream_key, worker._consumer_group, "1700000000000-0"
        )

    @pytest.mark.asyncio
    async def test_discards_message_above_threshold(self) -> None:
        redis = _make_redis()
        worker = _make_worker(redis, pel_max_requeue_count=3)

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
        worker = _make_worker(
            redis, pel_stuck_timeout_seconds=60, pel_xautoclaim_count=100
        )

        await worker._scan_and_requeue()

        redis.xautoclaim.assert_awaited_once_with(
            worker._stream_key,
            worker._consumer_group,
            PEL_CONSUMER_NAME,
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

        assert redis.xadd.await_count == 2
        assert redis.xack.await_count == 2

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
        redis.xadd.assert_awaited_once()
        redis.xack.assert_awaited_once_with(
            worker._stream_key, worker._consumer_group, "1700000000002-0"
        )

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

    @pytest.mark.asyncio
    async def test_handles_deleted_ids_without_xack_or_requeue(self) -> None:
        """Redis 7.0+ returns ghost PEL entries in the third response element."""
        redis = _make_redis()
        redis.xautoclaim = AsyncMock(
            return_value=("0-0", [], ["1700000000999-0", "1700000000998-0"])
        )

        worker = _make_worker(redis)
        await worker._scan_and_requeue()

        redis.xadd.assert_not_awaited()
        redis.xack.assert_not_awaited()

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

        redis.xadd.assert_awaited_once()
        assert redis.xack.await_count == 2
        assert (
            worker._stream_key,
            worker._consumer_group,
            "1700000000999-0",
        ) in [call.args for call in redis.xack.await_args_list]

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

        redis.xadd.assert_awaited_once()
        assert redis.xadd.await_args.args[1]["requeue_count"] == "1"
        redis.xack.assert_awaited_once_with(
            worker._stream_key, worker._consumer_group, "1700000000002-0"
        )


# ---------------------------------------------------------------------------
# PELRequeueWorker — worker loop
# ---------------------------------------------------------------------------


class TestPELWorkerLoop:
    @pytest.mark.asyncio
    async def test_worker_stops_cleanly(self) -> None:
        redis = _make_redis()
        scan_calls: list[int] = []

        async def fake_scan() -> None:
            scan_calls.append(1)

        worker = _make_worker(redis, pel_scan_interval_seconds=0.05)
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

        worker_a = _make_worker(redis, pel_scan_interval_seconds=0.05)
        worker_b = _make_worker(redis, pel_scan_interval_seconds=0.05)

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
            pel_scan_interval_seconds=0.01,
            pel_lifecycle_error_backoff_seconds=0.05,
        )
        worker._scan_and_requeue = failing_scan  # type: ignore[method-assign]
        await worker.start()

        await asyncio.sleep(0.2)
        await worker.stop()

        assert len(scan_calls) >= 2, "Expected retries after error backoff"
