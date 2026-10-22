import pytest
from pydantic import ValidationError

from port_ocean.config.settings import CentralizedRateLimiterSettings


def test_defaults_disabled() -> None:
    settings = CentralizedRateLimiterSettings()
    assert settings.enabled is False
    assert settings.redis.url == "redis://localhost:6379"


def test_nested_redis_url() -> None:
    # Constructor expects RedisConnectionSettings; model_validate takes the dict.
    settings = CentralizedRateLimiterSettings.model_validate(
        {"enabled": True, "redis": {"url": "redis://localhost:6379/0"}}
    )
    assert settings.redis.url == "redis://localhost:6379/0"


def test_rejects_rediss_url_without_tls_enabled() -> None:
    with pytest.raises(ValidationError, match="enable_tls is False"):
        # Constructor expects RedisConnectionSettings; model_validate takes the dict.
        CentralizedRateLimiterSettings.model_validate(
            {"enabled": True, "redis": {"url": "rediss://localhost:6379"}}
        )
