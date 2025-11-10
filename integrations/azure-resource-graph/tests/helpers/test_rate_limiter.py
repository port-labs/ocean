import pytest

from azure_integration.helpers.rate_limiter import AdaptiveTokenBucketRateLimiter


@pytest.mark.asyncio
async def test_adaptive_rate_limiter_adjusts_down_and_up() -> None:
    limiter = AdaptiveTokenBucketRateLimiter(
        capacity=100,
        refill_rate=10.0,
        adjustment_cooldown=0.0,
    )

    # Force a reduction when quota is low
    limiter.adjust_from_headers({"x-ms-ratelimit-remaining-tenant-reads": "5"})
    assert limiter._adaptive_refill_rate < 10.0

    # Then allow recovery when quota is high
    before = limiter._adaptive_refill_rate
    limiter.adjust_from_headers({"x-ms-ratelimit-remaining-tenant-reads": "90"})
    assert limiter._adaptive_refill_rate >= before
    assert limiter._adaptive_refill_rate <= limiter.refill_rate


@pytest.mark.asyncio
async def test_adaptive_rate_limiter_limit_consumes_without_wait() -> None:
    limiter = AdaptiveTokenBucketRateLimiter(capacity=5, refill_rate=100.0)
    # Preload tokens and ensure we can pass through context
    async with limiter.limit():
        pass
