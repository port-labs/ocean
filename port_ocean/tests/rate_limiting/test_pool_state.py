import time

from port_ocean.rate_limiting.models import CentralizedRateLimitState
from port_ocean.rate_limiting.models import SyncTier
from port_ocean.rate_limiting.pool_state import (
    pool_state_from_redis_hash,
    record_hash_mapping,
    should_back_off_for_sync_tier,
    wait_seconds_until_quota_reset,
    wait_seconds_while_pool_blocked,
)


def test_untracked_pool_when_limit_missing() -> None:
    state = pool_state_from_redis_hash({b"remaining": b"40"})
    assert state.limit is None


def test_tier_low_backs_off_when_ratio_at_ceiling() -> None:
    state = pool_state_from_redis_hash(
        {b"remaining": b"25", b"limit": b"100"},
    )
    assert should_back_off_for_sync_tier(SyncTier.LOW, state) is True


def test_tier_high_allows_while_remaining_positive() -> None:
    state = pool_state_from_redis_hash(
        {b"remaining": b"1", b"limit": b"100"},
    )
    assert should_back_off_for_sync_tier(SyncTier.HIGH, state) is False


def test_wait_seconds_while_pool_blocked() -> None:
    now = time.time()
    state = pool_state_from_redis_hash(
        {b"blocked_until": str(now + 30).encode(), b"limit": b"1", b"remaining": b"1"},
    )
    wait = wait_seconds_while_pool_blocked(state.blocked_until, now)
    assert wait is not None
    assert 29 < wait <= 30


def test_record_hash_mapping_sets_block_on_rate_limited() -> None:
    now = time.time()
    mapping = record_hash_mapping(
        CentralizedRateLimitState(remaining=0, limit=100),
        is_rate_limited=True,
        now=now,
    )
    assert float(mapping["blocked_until"]) > now


def test_wait_seconds_until_quota_reset() -> None:
    now = time.time()
    state = pool_state_from_redis_hash(
        {
            b"remaining": b"0",
            b"limit": b"100",
            b"reset_at": str(now + 45).encode(),
        },
    )
    assert wait_seconds_until_quota_reset(state.reset_at, now) == 45
