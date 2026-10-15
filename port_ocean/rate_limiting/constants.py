DEFAULT_RATE_LIMIT_POOL = "default"

# httpx.Request.extensions keys (integration code may set pool per request later).
CENTRALIZED_RATE_LIMIT_POOL_EXTENSION = "ocean_centralized_rate_limit_pool"
SKIP_CENTRALIZED_RATE_LIMIT_EXTENSION = "ocean_skip_centralized_rate_limit"

REDIS_KEY_PREFIX = "ratelimit"
