DEFAULT_RATE_LIMIT_POOL = "default"

REDIS_KEY_PREFIX = "ratelimit"

# When record marks is_rate_limited without blocked_until (integration sets deadline).
DEFAULT_RATE_LIMITED_BLOCK_SECONDS = 60
