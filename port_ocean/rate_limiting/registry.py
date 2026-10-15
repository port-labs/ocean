from typing import Optional

from loguru import logger

from port_ocean.rate_limiting.coordinator import CentralizedRateLimiter

_limiter: Optional[CentralizedRateLimiter] = None
_registered_type: Optional[str] = None


def register_centralized_rate_limiter(limiter: CentralizedRateLimiter) -> None:
    global _limiter, _registered_type
    new_type = type(limiter.backend).__name__
    if _limiter is not None and _registered_type != new_type:
        logger.warning(
            "Centralized rate limiter already registered; keeping the first backend",
            existing=_registered_type,
            ignored=new_type,
        )
        return
    _limiter = limiter
    _registered_type = new_type


def get_centralized_rate_limiter() -> Optional[CentralizedRateLimiter]:
    return _limiter


def clear_centralized_rate_limiter() -> None:
    global _limiter, _registered_type
    _limiter = None
    _registered_type = None
