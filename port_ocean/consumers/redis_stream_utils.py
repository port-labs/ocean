from redis.exceptions import ResponseError


def is_missing_stream_or_group_error(error: Exception) -> bool:
    """Return True when Redis reports a missing stream key or consumer group."""
    if not isinstance(error, ResponseError):
        return False

    return "NOGROUP" in str(error).upper()
