from port_ocean.rate_limiting.centralized_rate_limiter import CentralizedRateLimiter
from port_ocean.rate_limiting.models import RateLimitAcquireDecision, SyncTier
from port_ocean.rate_limiting.pool_state import PoolRedisState

NOW = 1_700_000_000.0


def _limiter() -> CentralizedRateLimiter:
    return CentralizedRateLimiter("org-test")


def test_expired_quota_allows_even_when_remaining_is_zero() -> None:
    state = PoolRedisState(
        limit=140,
        remaining=0,
        reset_at=NOW - 10,
        blocked_until=0,
    )
    result = _limiter()._admission_from_pool(state, SyncTier.LOW, NOW)
    assert result is not None
    assert result.decision == RateLimitAcquireDecision.ALLOW


def test_missing_reset_at_allows_instead_of_spinning() -> None:
    state = PoolRedisState(limit=100, remaining=0, reset_at=0, blocked_until=0)
    result = _limiter()._admission_from_pool(state, SyncTier.MEDIUM, NOW)
    assert result is not None
    assert result.decision == RateLimitAcquireDecision.ALLOW


def test_future_reset_still_backs_off_for_empty_quota() -> None:
    state = PoolRedisState(
        limit=100,
        remaining=0,
        reset_at=NOW + 45,
        blocked_until=0,
    )
    result = _limiter()._admission_from_pool(state, SyncTier.HIGH, NOW)
    assert result is not None
    assert result.decision == RateLimitAcquireDecision.BLOCK
    assert result.wait_seconds == 45


def test_real_block_holds_after_quota_window_expired() -> None:
    state = PoolRedisState(
        limit=140,
        remaining=0,
        reset_at=NOW - 10,
        blocked_until=NOW + 30,
    )
    result = _limiter()._admission_from_pool(state, SyncTier.HIGH, NOW)
    assert result is not None
    assert result.decision == RateLimitAcquireDecision.BLOCK
    assert result.wait_seconds == 30
