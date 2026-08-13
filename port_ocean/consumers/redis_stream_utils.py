import asyncio

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


async def ack_and_finalize_stream_entry(
    redis: RedisClient,
    *,
    stream_key: str,
    consumer_group: str,
    message_id: str,
) -> None:
    """Ack a stream entry and delete it in one transaction."""
    try:
        async with redis.pipeline(transaction=True) as pipe:
            await pipe.xack(stream_key, consumer_group, message_id)
            await pipe.xdel(stream_key, message_id)
            await pipe.execute()
    except ResponseError as error:
        if is_missing_stream_or_group_error(error):
            logger.warning(
                "Redis stream or consumer group missing during ack finalize",
                stream_key=stream_key,
                consumer_group=consumer_group,
                message_id=message_id,
                error=str(error),
            )
        raise
