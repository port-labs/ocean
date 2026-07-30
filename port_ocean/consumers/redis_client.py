from typing import Any

from loguru import logger
from redis.asyncio import Redis
from redis.asyncio.cluster import RedisCluster

RedisClient = Redis | RedisCluster


async def is_redis_cluster_enabled(redis_client: Redis) -> bool:
    """Return True when the connected Redis instance has cluster mode enabled."""
    cluster_info = await redis_client.info("cluster")
    return bool(cluster_info.get("cluster_enabled"))


async def create_redis_client(url: str, **kwargs: Any) -> RedisClient:
    """Connect to Redis, using a cluster client when cluster mode is enabled."""
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
