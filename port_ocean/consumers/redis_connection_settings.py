from typing import Self
from urllib.parse import urlparse

from pydantic import ConfigDict, Field, model_validator

from port_ocean.config.base import BaseOceanModel, sensitive_field


class RedisConnectionSettings(BaseOceanModel):
    """Shared Redis connection/TLS settings (live-events streams, centralized rate limiter)."""

    model_config = ConfigDict(extra="allow")

    url: str = Field(default="redis://localhost:6379")
    username: str | None = None
    password: str | None = sensitive_field(default=None)
    enable_tls: bool = False
    ca: str | None = Field(
        default=None,
        description="Base64-encoded PEM CA certificate bundle for TLS verification.",
    )
    cert: str | None = Field(
        default=None,
        description="Base64-encoded PEM client certificate for mutual TLS.",
    )
    private_key: str | None = sensitive_field(
        default=None,
        description="Base64-encoded PEM private key for mutual TLS.",
    )
    connection_startup_max_retries: int = Field(
        default=5,
        ge=0,
        description=(
            "Maximum number of connection retries when establishing the "
            "initial Redis client at startup."
        ),
    )
    connection_startup_initial_backoff_seconds: float = Field(
        default=1.0,
        gt=0,
        description=(
            "Initial delay in seconds before the first Redis startup "
            "connection retry."
        ),
    )
    connection_startup_exponential_base: float = Field(
        default=2.0,
        gt=0,
        description=(
            "Exponential base used to calculate Redis startup connection "
            "retry delays."
        ),
    )

    @model_validator(mode="after")
    def validate_tls_settings(self) -> Self:
        scheme = urlparse(self.url).scheme.lower()
        uses_tls_scheme = scheme == "rediss"

        if self.enable_tls and not uses_tls_scheme:
            raise ValueError(
                "enable_tls is True but the Redis URL does not use the rediss:// "
                "scheme. Use a rediss:// URL or set enable_tls to False."
            )
        if not self.enable_tls and uses_tls_scheme:
            raise ValueError(
                "The Redis URL uses rediss:// but enable_tls is False. "
                "Set enable_tls to True or use a redis:// URL."
            )

        has_cert = bool(self.cert)
        has_private_key = bool(self.private_key)
        if has_cert != has_private_key:
            raise ValueError(
                "Redis mutual TLS requires both cert and private_key to be set."
            )

        return self
