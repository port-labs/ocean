from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from port_ocean.config.settings import CentralizedRateLimiterSettings
from port_ocean.consumers.redis_client import create_redis_client_with_retry
from port_ocean.consumers.redis_connection import RedisConnectionHelper
from port_ocean.rate_limiting.centralized_rate_limiter import CentralizedRateLimiter

if TYPE_CHECKING:
    from port_ocean.ocean import Ocean


async def setup_centralized_rate_limiter(
    app: Ocean,
    settings: CentralizedRateLimiterSettings,
    *,
    org_id: str,
) -> None:
    """Initialize the centralized rate limiter on the Ocean app instance."""
    if not settings.enabled:
        return

    if app.centralized_rate_limiter is not None:
        message = (
            "Centralized rate limiter is already registered on this Ocean app; "
            "setup_centralized_rate_limiter must not be called twice"
        )
        logger.error(message)
        raise RuntimeError(message)

    redis_settings = settings.redis
    redis_helper = RedisConnectionHelper()
    try:
        client_kwargs = redis_helper.client_kwargs(redis_settings)
        redis_client = await create_redis_client_with_retry(
            redis_settings.url,
            max_retries=redis_settings.connection_startup_max_retries,
            initial_backoff_seconds=redis_settings.connection_startup_initial_backoff_seconds,
            exponential_base=redis_settings.connection_startup_exponential_base,
            **client_kwargs,
        )
        limiter = CentralizedRateLimiter(org_id, redis_client, redis_helper)
        await limiter.initialize()
        app.centralized_rate_limiter = limiter
        logger.info("Centralized rate limiter enabled with Redis")
    except Exception as error:
        redis_helper.cleanup()
        logger.warning(
            "Failed to connect to centralized rate limiter Redis; using no-op limiter",
            error=str(error),
        )
        app.centralized_rate_limiter = CentralizedRateLimiter(org_id, None)


async def teardown_centralized_rate_limiter(app: Ocean) -> None:
    """Release Redis resources opened by setup_centralized_rate_limiter."""
    limiter = app.centralized_rate_limiter
    if limiter is not None:
        try:
            await limiter.close()
        except Exception as error:
            logger.warning(
                "Error closing centralized rate limiter Redis client",
                error=str(error),
            )
    app.centralized_rate_limiter = None
