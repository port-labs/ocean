from unittest.mock import AsyncMock

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError
from redis.exceptions import TimeoutError as RedisTimeoutError

from port_ocean.consumers.redis_stream_utils import (
    ACK_AND_FINALIZE_STREAM_ENTRY_SCRIPT,
    ack_and_finalize_stream_entry,
    cleanup_idle_consumers_from_group,
    ensure_consumer_group,
    is_missing_stream_or_group_error,
    is_redis_connection_error,
)


def _make_redis_for_ack_finalize() -> AsyncMock:
    redis = AsyncMock()
    redis.eval = AsyncMock(return_value=1)
    return redis


class TestIsMissingStreamOrGroupError:
    @pytest.mark.parametrize(
        "message",
        [
            "NOGROUP No such key 'stream' or consumer group 'group'",
            "nogroup consumer group name does not exist",
        ],
    )
    def test_returns_true_for_missing_stream_or_group(self, message: str) -> None:
        assert is_missing_stream_or_group_error(ResponseError(message)) is True

    def test_returns_false_for_other_response_errors(self) -> None:
        assert (
            is_missing_stream_or_group_error(ResponseError("BUSYGROUP already exists"))
            is False
        )

    def test_returns_false_for_non_response_errors(self) -> None:
        assert is_missing_stream_or_group_error(RuntimeError("boom")) is False


class TestAckAndFinalizeStreamEntry:
    @pytest.mark.asyncio
    async def test_acks_and_deletes_entry(self) -> None:
        redis = _make_redis_for_ack_finalize()

        await ack_and_finalize_stream_entry(
            redis,
            stream_key="stream",
            consumer_group="test.integration",
            message_id="1700000000000-0",
        )

        redis.eval.assert_awaited_once_with(
            ACK_AND_FINALIZE_STREAM_ENTRY_SCRIPT,
            1,
            "stream",
            "test.integration",
            "1700000000000-0",
        )

    @pytest.mark.asyncio
    async def test_swallows_missing_stream_error_from_eval(self) -> None:
        redis = _make_redis_for_ack_finalize()
        redis.eval = AsyncMock(
            side_effect=ResponseError("NOGROUP No such key 'stream' or consumer group")
        )

        await ack_and_finalize_stream_entry(
            redis,
            stream_key="stream",
            consumer_group="test.integration",
            message_id="1700000000000-0",
        )

        redis.eval.assert_awaited_once()


class TestEnsureConsumerGroup:
    @pytest.mark.asyncio
    async def test_sets_ttl_when_stream_is_created(self) -> None:
        redis = AsyncMock()
        redis.exists = AsyncMock(return_value=0)
        redis.xgroup_create = AsyncMock()
        redis.expire = AsyncMock()

        await ensure_consumer_group(
            redis,
            stream_key="stream",
            consumer_group="test.integration",
            stream_ttl_seconds=3600,
        )

        redis.expire.assert_awaited_once_with("stream", 3600)
        assert redis.xgroup_create.await_args is not None
        assert redis.xgroup_create.await_args.kwargs["id"] == "$"

    @pytest.mark.asyncio
    async def test_uses_start_id_zero_when_stream_already_exists(self) -> None:
        redis = AsyncMock()
        redis.exists = AsyncMock(return_value=1)
        redis.xgroup_create = AsyncMock()
        redis.expire = AsyncMock()

        await ensure_consumer_group(
            redis,
            stream_key="stream",
            consumer_group="test.integration",
            stream_ttl_seconds=3600,
        )

        assert redis.xgroup_create.await_args is not None
        assert redis.xgroup_create.await_args.kwargs["id"] == "0"

    @pytest.mark.asyncio
    async def test_skips_ttl_when_stream_already_exists(self) -> None:
        redis = AsyncMock()
        redis.exists = AsyncMock(return_value=1)
        redis.xgroup_create = AsyncMock()
        redis.expire = AsyncMock()

        await ensure_consumer_group(
            redis,
            stream_key="stream",
            consumer_group="test.integration",
            stream_ttl_seconds=3600,
        )

        redis.expire.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_ignores_busygroup(self) -> None:
        redis = AsyncMock()
        redis.exists = AsyncMock(return_value=1)
        redis.xgroup_create = AsyncMock(
            side_effect=ResponseError("BUSYGROUP Consumer Group name already exists")
        )
        redis.expire = AsyncMock()

        await ensure_consumer_group(
            redis,
            stream_key="stream",
            consumer_group="test.integration",
            stream_ttl_seconds=3600,
        )

        redis.expire.assert_not_awaited()


class TestCleanupIdleConsumersFromGroup:
    @pytest.mark.asyncio
    async def test_removes_idle_consumer_with_no_pending_messages(self) -> None:
        redis = AsyncMock()
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

        removed = await cleanup_idle_consumers_from_group(
            redis,
            stream_key="stream",
            consumer_group="test.integration",
            idle_threshold_ms=3600_000,
            protected_consumer_names=frozenset(),
        )

        assert removed == 1
        redis.xgroup_delconsumer.assert_awaited_once_with(
            "stream",
            "test.integration",
            "integration-dead-pod",
        )

    @pytest.mark.asyncio
    async def test_skips_protected_consumer_names(self) -> None:
        redis = AsyncMock()
        redis.xinfo_consumers = AsyncMock(
            return_value=[
                {
                    "name": "stream-maintenance-worker",
                    "pending": 0,
                    "idle": 5_000_000,
                },
                {
                    "name": "integration-live-pod",
                    "pending": 0,
                    "idle": 5_000_000,
                },
            ]
        )
        redis.xgroup_delconsumer = AsyncMock(return_value=0)

        removed = await cleanup_idle_consumers_from_group(
            redis,
            stream_key="stream",
            consumer_group="test.integration",
            idle_threshold_ms=3600_000,
            protected_consumer_names=frozenset(
                {"stream-maintenance-worker", "integration-live-pod"}
            ),
        )

        assert removed == 0
        redis.xgroup_delconsumer.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_skips_consumers_with_pending_messages(self) -> None:
        redis = AsyncMock()
        redis.xinfo_consumers = AsyncMock(
            return_value=[
                {
                    "name": "integration-dead-pod",
                    "pending": 2,
                    "idle": 5_000_000,
                }
            ]
        )
        redis.xgroup_delconsumer = AsyncMock(return_value=0)

        removed = await cleanup_idle_consumers_from_group(
            redis,
            stream_key="stream",
            consumer_group="test.integration",
            idle_threshold_ms=3600_000,
            protected_consumer_names=frozenset(),
        )

        assert removed == 0
        redis.xgroup_delconsumer.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_skips_consumers_below_idle_threshold(self) -> None:
        redis = AsyncMock()
        redis.xinfo_consumers = AsyncMock(
            return_value=[
                {
                    "name": "integration-recent-pod",
                    "pending": 0,
                    "idle": 1000,
                }
            ]
        )
        redis.xgroup_delconsumer = AsyncMock(return_value=0)

        removed = await cleanup_idle_consumers_from_group(
            redis,
            stream_key="stream",
            consumer_group="test.integration",
            idle_threshold_ms=3600_000,
            protected_consumer_names=frozenset(),
        )

        assert removed == 0
        redis.xgroup_delconsumer.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_swallows_missing_stream_error(self) -> None:
        redis = AsyncMock()
        redis.xinfo_consumers = AsyncMock(
            side_effect=ResponseError("NOGROUP No such key 'stream' or consumer group")
        )

        removed = await cleanup_idle_consumers_from_group(
            redis,
            stream_key="stream",
            consumer_group="test.integration",
            idle_threshold_ms=3600_000,
            protected_consumer_names=frozenset(),
        )

        assert removed == 0
        redis.xgroup_delconsumer.assert_not_awaited()


class TestIsRedisConnectionError:
    @pytest.mark.parametrize(
        "error",
        [
            RedisConnectionError("connection refused"),
            RedisTimeoutError("timed out"),
            TimeoutError(),
            ConnectionError("broken pipe"),
            OSError("network unreachable"),
        ],
    )
    def test_returns_true_for_connection_errors(self, error: BaseException) -> None:
        assert is_redis_connection_error(error) is True

    def test_returns_false_for_other_errors(self) -> None:
        assert is_redis_connection_error(ResponseError("NOGROUP")) is False
        assert is_redis_connection_error(RuntimeError("boom")) is False
