from loguru import logger

from port_ocean.config.settings import CentralizedRateLimiterSettings
from port_ocean.consumers.redis_client import create_redis_client_with_retry
from port_ocean.consumers.redis_connection import RedisConnectionHelper
from port_ocean.rate_limiting.backend import NoOpCentralizedRateLimiterBackend
from port_ocean.rate_limiting.coordinator import CentralizedRateLimiter
from port_ocean.rate_limiting.redis_backend import RedisCentralizedRateLimiterBackend
from port_ocean.rate_limiting.registry import register_centralized_rate_limiter

_startup_warning_logged = False
_redis_connection_helper = RedisConnectionHelper()


async def setup_centralized_rate_limiter(
    settings: CentralizedRateLimiterSettings,
) -> None:
    """Initialize the process-wide centralized rate limiter from Ocean config."""
    global _startup_warning_logged

    if not settings.enabled:
        register_centralized_rate_limiter(
            CentralizedRateLimiter(NoOpCentralizedRateLimiterBackend())
        )
        return

    redis_settings = settings.redis
    try:
        client_kwargs = _redis_connection_helper.client_kwargs(redis_settings)
        redis_client = await create_redis_client_with_retry(
            redis_settings.url,
            max_retries=redis_settings.connection_startup_max_retries,
            initial_backoff_seconds=redis_settings.connection_startup_initial_backoff_seconds,
            exponential_base=redis_settings.connection_startup_exponential_base,
            **client_kwargs,
        )
        backend = RedisCentralizedRateLimiterBackend(redis_client)
        register_centralized_rate_limiter(CentralizedRateLimiter(backend))
        logger.info("Centralized rate limiter enabled with Redis backend")
    except Exception as error:
        _redis_connection_helper.cleanup()
        if not _startup_warning_logged:
            logger.warning(
                "Failed to connect to centralized rate limiter Redis; using no-op backend",
                error=str(error),
            )
            _startup_warning_logged = True
        register_centralized_rate_limiter(
            CentralizedRateLimiter(NoOpCentralizedRateLimiterBackend())
        )
