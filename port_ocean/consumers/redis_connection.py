import os
import tempfile
from base64 import b64decode
from typing import Any

from redis.asyncio.connection import SSLConnection

from port_ocean.consumers.redis_connection_settings import RedisConnectionSettings


class RedisConnectionHelper:
    """Builds redis-py client kwargs and manages temporary mTLS PEM files."""

    def __init__(self) -> None:
        self._ssl_cert_file: str | None = None
        self._ssl_key_file: str | None = None

    def _materialize_client_tls_files(self, settings: RedisConnectionSettings) -> None:
        self.cleanup()
        if not settings.cert or not settings.private_key:
            return

        cert_pem = b64decode(settings.cert).decode()
        key_pem = b64decode(settings.private_key).decode()

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
            kwargs["ssl_ca_data"] = b64decode(settings.ca).decode()

        self._materialize_client_tls_files(settings)
        if self._ssl_cert_file and self._ssl_key_file:
            kwargs["ssl_certfile"] = self._ssl_cert_file
            kwargs["ssl_keyfile"] = self._ssl_key_file

        return kwargs
