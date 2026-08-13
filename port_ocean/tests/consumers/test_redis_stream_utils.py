import asyncio
from unittest.mock import AsyncMock

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError
from redis.exceptions import TimeoutError as RedisTimeoutError

from port_ocean.consumers.redis_stream_utils import (
    ack_and_finalize_stream_entry,
    ensure_consumer_group,
    is_missing_stream_or_group_error,
    is_redis_connection_error,
)


def _make_redis_for_ack_finalize() -> AsyncMock:
    redis = AsyncMock()
    redis.xack = AsyncMock(return_value=1)
    redis.xdel = AsyncMock(return_value=1)
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

        redis.xack.assert_awaited_once_with(
            "stream", "test.integration", "1700000000000-0"
        )
        redis.xdel.assert_awaited_once_with("stream", "1700000000000-0")

    @pytest.mark.asyncio
    async def test_swallows_missing_stream_error_from_xack(self) -> None:
        redis = _make_redis_for_ack_finalize()
        redis.xack = AsyncMock(
            side_effect=ResponseError("NOGROUP No such key 'stream' or consumer group")
        )

        await ack_and_finalize_stream_entry(
            redis,
            stream_key="stream",
            consumer_group="test.integration",
            message_id="1700000000000-0",
        )

        redis.xack.assert_awaited_once()
        redis.xdel.assert_not_awaited()


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


class TestIsRedisConnectionError:
    @pytest.mark.parametrize(
        "error",
        [
            RedisConnectionError("connection refused"),
            RedisTimeoutError("timed out"),
            asyncio.TimeoutError(),
            ConnectionError("broken pipe"),
            OSError("network unreachable"),
        ],
    )
    def test_returns_true_for_connection_errors(self, error: BaseException) -> None:
        assert is_redis_connection_error(error) is True

    def test_returns_false_for_other_errors(self) -> None:
        assert is_redis_connection_error(ResponseError("NOGROUP")) is False
        assert is_redis_connection_error(RuntimeError("boom")) is False
