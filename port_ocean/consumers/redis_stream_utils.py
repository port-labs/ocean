import asyncio
from collections.abc import Awaitable
from typing import Any, cast

from loguru import logger
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError
from redis.exceptions import TimeoutError as RedisTimeoutError

from port_ocean.consumers.redis_client import RedisClient

_REDIS_CONNECTION_ERRORS = (
    RedisConnectionError,
    RedisTimeoutError,
    asyncio.TimeoutError,
    ConnectionError,
    OSError,
)


def is_redis_connection_error(error: BaseException) -> bool:
    """Return True when the error indicates Redis is unreachable or disconnected."""
    return isinstance(error, _REDIS_CONNECTION_ERRORS)


def is_missing_stream_or_group_error(error: Exception) -> bool:
    """Return True when Redis reports a missing stream key or consumer group."""
    if not isinstance(error, ResponseError):
        return False

    return "NOGROUP" in str(error).upper()


async def ensure_consumer_group(
    redis: RedisClient,
    *,
    stream_key: str,
    consumer_group: str,
    stream_ttl_seconds: int | None = None,
) -> None:
    """Create the stream and consumer group if they do not exist."""
    stream_existed = bool(await redis.exists(stream_key))
    consumer_group_created = False
    try:
        await redis.xgroup_create(
            stream_key,
            consumer_group,
            id="$",
            mkstream=True,
        )
        consumer_group_created = True
    except ResponseError as error:
        if "BUSYGROUP" not in str(error):
            raise

    if consumer_group_created and not stream_existed and stream_ttl_seconds is not None:
        await redis.expire(stream_key, stream_ttl_seconds)
        logger.info(
            "Set TTL on newly created Redis stream",
            stream_key=stream_key,
            stream_ttl_seconds=stream_ttl_seconds,
        )


ACK_AND_FINALIZE_STREAM_ENTRY_SCRIPT = """
redis.call('XACK', KEYS[1], ARGV[1], ARGV[2])
return redis.call('XDEL', KEYS[1], ARGV[2])
"""

REQUEUE_STREAM_ENTRY_SCRIPT = """
redis.call('XADD', KEYS[1], '*', unpack(ARGV, 3))
redis.call('XACK', KEYS[1], ARGV[1], ARGV[2])
return redis.call('XDEL', KEYS[1], ARGV[2])
"""


async def _eval_lua_script(
    redis: RedisClient,
    script: str,
    keys: list[str],
    args: list[str],
) -> Any:
    """Run a Lua script on Redis so multiple commands execute atomically.

    Stream ack/finalize and requeue paths issue several commands (e.g. XACK + XDEL).
    Redis runs each EVAL script as a single atomic unit, so partial updates cannot
    leave entries half-processed if another client or failure interleaves.
    """
    return await cast(
        Awaitable[Any],
        redis.eval(script, len(keys), *keys, *args),
    )


async def ack_and_finalize_stream_entry(
    redis: RedisClient,
    *,
    stream_key: str,
    consumer_group: str,
    message_id: str,
) -> None:
    """Atomically ack a stream entry and delete it using a Lua script."""
    try:
        await _eval_lua_script(
            redis,
            ACK_AND_FINALIZE_STREAM_ENTRY_SCRIPT,
            [stream_key],
            [consumer_group, message_id],
        )
    except ResponseError as error:
        if not is_missing_stream_or_group_error(error):
            raise
        logger.warning(
            "Redis stream or consumer group missing during ack finalize",
            stream_key=stream_key,
            consumer_group=consumer_group,
            message_id=message_id,
            error=str(error),
        )


async def requeue_stream_entry(
    redis: RedisClient,
    *,
    stream_key: str,
    consumer_group: str,
    message_id: str,
    fields: dict[str, str],
) -> None:
    """Atomically re-enqueue a stream entry and finalize the original via Lua."""
    field_items: list[str] = []
    for key, value in fields.items():
        field_items.extend((key, value))

    await _eval_lua_script(
        redis,
        REQUEUE_STREAM_ENTRY_SCRIPT,
        [stream_key],
        [consumer_group, message_id, *field_items],
    )
