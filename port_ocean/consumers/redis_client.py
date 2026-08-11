import asyncio
from typing import Any

from loguru import logger
from redis.asyncio import Redis
from redis.asyncio.cluster import RedisCluster

RedisClient = Redis | RedisCluster


async def is_redis_cluster_enabled(redis_client: Redis) -> bool:
    """Return True when the connected Redis instance has cluster mode enabled."""
    cluster_info = await redis_client.info("cluster")
    return bool(cluster_info.get("cluster_enabled"))


async def _create_redis_client_once(url: str, **kwargs: Any) -> RedisClient:
    """Connect to Redis once, using a cluster client when cluster mode is enabled."""
    client = Redis.from_url(url, **kwargs)
    try:
        if await is_redis_cluster_enabled(client):
            await client.aclose()
            logger.info("Detected Redis cluster mode, using RedisCluster client")
            return RedisCluster.from_url(url, **kwargs)
    except Exception:
        await client.aclose()
        raise

    logger.info("Using standalone Redis client")
    return client


async def create_redis_client(url: str, **kwargs: Any) -> RedisClient:
    """Connect to Redis, using a cluster client when cluster mode is enabled."""
    try:
        return await _create_redis_client_once(url, **kwargs)
    except Exception as error:
        logger.exception(
            "Failed to connect to Redis",
            error=str(error),
        )
        raise


async def create_redis_client_with_retry(
    url: str,
    *,
    max_retries: int,
    initial_backoff_seconds: float,
    exponential_base: float,
    **kwargs: Any,
) -> RedisClient:
    """Connect to Redis with exponential backoff retries at startup."""
    for attempt in range(max_retries + 1):
        try:
            return await _create_redis_client_once(url, **kwargs)
        except Exception as error:
            if attempt >= max_retries:
                logger.exception(
                    "Failed to connect to Redis after exhausting startup retries",
                    error=str(error),
                    max_retries=max_retries,
                )
                raise
            delay_seconds = initial_backoff_seconds * (exponential_base**attempt)
            logger.warning(
                f"Failed to connect to Redis at startup, retrying in {delay_seconds:.2f} seconds",
                attempt=attempt + 1,
                max_retries=max_retries,
                delay_seconds=delay_seconds,
                error=str(error),
            )
            await asyncio.sleep(delay_seconds)

    raise RuntimeError("Unreachable: Redis startup retry loop exited unexpectedly")
