import asyncio

from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError
from redis.exceptions import TimeoutError as RedisTimeoutError

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
