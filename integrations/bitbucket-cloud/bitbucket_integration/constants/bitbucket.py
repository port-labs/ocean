from aiolimiter import AsyncLimiter

# Bitbucket API rate limit: 1000 requests per hour
BITBUCKET_LIMIT = 1000
BITBUCKET_TIME_PERIOD = 3600  # 1 hour
RATE_LIMITER = AsyncLimiter(max_rate=BITBUCKET_LIMIT, time_period=BITBUCKET_TIME_PERIOD)
