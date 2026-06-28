"""Tests for PELRequeueWorker."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from port_ocean.consumers.pel_requeue import PELRequeueWorker
from port_ocean.consumers.pel_requeue.settings import (
    PELRequeueWorkerSettings,
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


def _default_settings(**overrides: Any) -> PELRequeueWorkerSettings:
    defaults = PELRequeueWorkerSettings(
        stream_key="test/live-events/raw/event-stream",
        consumer_group="test.integration",
        pod_id="pod-abc",
        stuck_timeout_ms=60_000,
        max_requeue_count=3,
        scan_interval_seconds=30.0,
        election_retry_seconds=0.05,
    )
    return replace(defaults, **overrides)


def _make_worker(redis: AsyncMock, **settings_overrides: Any) -> PELRequeueWorker:
    return PELRequeueWorker(redis, _default_settings(**settings_overrides))


# ---------------------------------------------------------------------------
# PELRequeueWorker — leader election integration
# ---------------------------------------------------------------------------


class TestPELRequeueWorkerLeaderElection:
    @pytest.mark.asyncio
    async def test_lifecycle_task_always_starts(self) -> None:
        """Every pod starts the lifecycle loop regardless of election outcome."""
        redis = _make_redis()
        redis.set = AsyncMock(return_value=True)

        worker = _make_worker(redis)
        await worker.start()

        assert worker._is_running is True
        assert worker._lifecycle_task is not None
        await worker.stop()

    @pytest.mark.asyncio
    async def test_lifecycle_task_starts_even_when_not_leader(self) -> None:
        """Non-leader pods must keep the lifecycle task alive to retry later."""
        redis = _make_redis()
        redis.set = AsyncMock(return_value=None)

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

        redis.set = flipping_set
        redis.get = AsyncMock(return_value="pod-abc")

        scanned: list[bool] = []

        worker = _make_worker(
            redis, election_retry_seconds=0.05, scan_interval_seconds=999.0
        )
        worker._scan_and_requeue = AsyncMock(  # type: ignore[method-assign]
            side_effect=lambda: scanned.append(True)
        )
        await worker.start()

        await asyncio.sleep(0.3)
        await worker.stop()

        assert call_count >= 2, "Expected at least two election attempts"
        assert len(scanned) >= 1, "Expected at least one scan after winning election"

    @pytest.mark.asyncio
    async def test_lifecycle_loop_backoffs_after_unexpected_error(self) -> None:
        redis = _make_redis()
        redis.set = AsyncMock(return_value=True)
        scan_calls: list[int] = []

        async def failing_scan() -> None:
            scan_calls.append(1)
            raise RuntimeError("redis unavailable")

        worker = _make_worker(
            redis,
            scan_interval_seconds=0.01,
            lifecycle_error_backoff_seconds=0.05,
        )
        worker._scan_and_requeue = failing_scan  # type: ignore[method-assign]
        await worker.start()

        await asyncio.sleep(0.2)
        await worker.stop()

        assert len(scan_calls) >= 2, "Expected retries after error backoff"


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
        sent_fields: dict[str, str] = call_args.args[1]
        assert sent_fields["requeue_count"] == "2"
        assert sent_fields["webhookPath"] == "/webhook"

        redis.xack.assert_awaited_once_with(
            worker._stream_key, worker._consumer_group, "1700000000000-0"
        )

    @pytest.mark.asyncio
    async def test_requeue_uses_transactional_pipeline(self) -> None:
        redis = _make_redis()
        worker = _make_worker(redis, max_requeue_count=3)

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
        worker = _make_worker(redis, max_requeue_count=3)

        fields = {"webhookPath": "/webhook", "payload": "{}", "headers": "{}"}
        await worker._handle_stuck_message("1700000000000-0", fields)

        sent_fields: dict[str, str] = redis.xadd.await_args.args[1]
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
        worker = _make_worker(redis, stuck_timeout_ms=60_000, xautoclaim_count=100)

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
    async def test_uses_configured_xautoclaim_count(self) -> None:
        redis = _make_redis()
        redis.xautoclaim = AsyncMock(return_value=("0-0", [], []))
        worker = _make_worker(redis, xautoclaim_count=25)

        await worker._scan_and_requeue()

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
