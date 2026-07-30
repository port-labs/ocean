"""
SSL verification helpers for Ocean HTTP clients.
"""

from __future__ import annotations

import ssl
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from port_ocean.config.settings import SslClientSettings


def _create_no_x509_strict_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    if hasattr(ssl, "VERIFY_X509_STRICT"):
        context.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return context


def resolve_verify_param(settings: "SslClientSettings") -> bool | ssl.SSLContext:
    if not settings.verify:
        return False

    if settings.x509.strict:
        return True

    return _create_no_x509_strict_context()
