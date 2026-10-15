from port_ocean.rate_limiting.backend import NoOpCentralizedRateLimiterBackend
from port_ocean.rate_limiting.coordinator import CentralizedRateLimiter
from port_ocean.rate_limiting.registry import (
    clear_centralized_rate_limiter,
    get_centralized_rate_limiter,
    register_centralized_rate_limiter,
)


def test_register_and_clear() -> None:
    clear_centralized_rate_limiter()
    assert get_centralized_rate_limiter() is None
    register_centralized_rate_limiter(
        CentralizedRateLimiter(NoOpCentralizedRateLimiterBackend())
    )
    assert get_centralized_rate_limiter() is not None
    clear_centralized_rate_limiter()
    assert get_centralized_rate_limiter() is None
