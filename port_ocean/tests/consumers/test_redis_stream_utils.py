import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError
from redis.exceptions import TimeoutError as RedisTimeoutError

from port_ocean.consumers.redis_stream_utils import (
    ack_and_finalize_stream_entry,
    is_missing_stream_or_group_error,
    is_redis_connection_error,
)


def _make_redis_with_pipeline() -> AsyncMock:
    redis = AsyncMock()
    redis.xack = AsyncMock(return_value=1)
    redis.xdel = AsyncMock(return_value=1)

    @asynccontextmanager
    async def fake_pipeline(
        *_args: object, **_kwargs: object
    ) -> AsyncIterator[AsyncMock]:
        pipe = AsyncMock()
        pipe.xack = redis.xack
        pipe.xdel = redis.xdel
        pipe.execute = AsyncMock(return_value=[1, 1])
        yield pipe

    redis.pipeline = fake_pipeline
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
    async def test_acks_and_deletes_entry_transactionally(self) -> None:
        redis = _make_redis_with_pipeline()

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
    async def test_raises_missing_stream_error_from_transaction(self) -> None:
        redis = _make_redis_with_pipeline()

        @asynccontextmanager
        async def failing_pipeline(
            *_args: object, **_kwargs: object
        ) -> AsyncIterator[AsyncMock]:
            pipe = AsyncMock()
            pipe.xack = redis.xack
            pipe.xdel = redis.xdel
            pipe.execute = AsyncMock(
                side_effect=ResponseError(
                    "NOGROUP No such key 'stream' or consumer group"
                )
            )
            yield pipe

        redis.pipeline = failing_pipeline

        with pytest.raises(ResponseError, match="NOGROUP"):
            await ack_and_finalize_stream_entry(
                redis,
                stream_key="stream",
                consumer_group="test.integration",
                message_id="1700000000000-0",
            )

        redis.xack.assert_awaited_once()


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
