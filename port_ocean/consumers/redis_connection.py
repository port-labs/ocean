import base64
import os
import tempfile
from typing import Any
from urllib.parse import urlparse

from pydantic import ConfigDict, Field, model_validator
from typing import Self

from port_ocean.config.base import BaseOceanModel, sensitive_field
from redis.asyncio.connection import SSLConnection


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


class RedisConnectionHelper:
    """Builds redis-py client kwargs and manages temporary mTLS PEM files."""

    def __init__(self) -> None:
        self._ssl_cert_file: str | None = None
        self._ssl_key_file: str | None = None

    @staticmethod
    def _decode_base64_pem(value: str) -> str:
        return base64.b64decode(value).decode()

    def _materialize_client_tls_files(self, settings: RedisConnectionSettings) -> None:
        self.cleanup()
        if not settings.cert or not settings.private_key:
            return

        cert_pem = self._decode_base64_pem(settings.cert)
        key_pem = self._decode_base64_pem(settings.private_key)

        cert_fd, cert_path = tempfile.mkstemp(suffix=".pem", prefix="redis-cert-")
        key_fd, key_path = tempfile.mkstemp(suffix=".pem", prefix="redis-key-")
        with os.fdopen(cert_fd, "w") as cert_file:
            cert_file.write(cert_pem)
        with os.fdopen(key_fd, "w") as key_file:
            key_file.write(key_pem)

        self._ssl_cert_file = cert_path
        self._ssl_key_file = key_path

    def cleanup(self) -> None:
        for path in (self._ssl_cert_file, self._ssl_key_file):
            if path and os.path.exists(path):
                os.unlink(path)
        self._ssl_cert_file = None
        self._ssl_key_file = None

    def client_kwargs(self, settings: RedisConnectionSettings) -> dict[str, Any]:
        """Connection kwargs for redis-py, including auth and TLS for cloud Redis."""
        self.cleanup()
        kwargs: dict[str, Any] = {
            "decode_responses": True,
            "legacy_responses": True,
            "socket_timeout": None,
        }
        if settings.username:
            kwargs["username"] = settings.username
        if settings.password is not None:
            kwargs["password"] = settings.password

        if not settings.enable_tls:
            return kwargs

        kwargs["connection_class"] = SSLConnection
        if settings.ca:
            kwargs["ssl_ca_data"] = self._decode_base64_pem(settings.ca)

        self._materialize_client_tls_files(settings)
        if self._ssl_cert_file and self._ssl_key_file:
            kwargs["ssl_certfile"] = self._ssl_cert_file
            kwargs["ssl_keyfile"] = self._ssl_key_file

        return kwargs
