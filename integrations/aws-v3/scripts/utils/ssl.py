"""SSL/TLS configuration for HTTP clients."""

from __future__ import annotations

import os
import ssl
from dataclasses import dataclass

import certifi


@dataclass(frozen=True)
class SslConfig:
    verify: bool = True
    ca_bundle: str | None = None

    def resolve_ca_bundle(self) -> str:
        return self.ca_bundle or os.environ.get("SSL_CA_BUNDLE") or certifi.where()

    def create_context(self) -> ssl.SSLContext | None:
        if not self.verify:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            return context
        return ssl.create_default_context(cafile=self.resolve_ca_bundle())
