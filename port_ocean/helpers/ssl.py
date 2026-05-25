"""
SSL verification helpers for Ocean HTTP clients.
"""

from __future__ import annotations

import ssl
from typing import TYPE_CHECKING, Literal

from loguru import logger

if TYPE_CHECKING:
    from port_ocean.config.settings import SslClientSettings

OceanSslRole = Literal["port", "third_party"]


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


def resolve_verify_param_for_ocean_role(role: OceanSslRole) -> bool | ssl.SSLContext:
    """Resolve httpx ``verify`` from Ocean config for the given client role.

    When Ocean is not initialized (e.g. standalone ``PortClient`` in unit tests or
    smoke helpers), fall back to ``verify=True`` — the same httpx default used
    before structured SSL settings. Production always initializes Ocean before
    any HTTP client is created.
    """
    from port_ocean.context.ocean import ocean

    if not ocean.initialized:
        return True

    ssl_settings = (
        ocean.config.ssl.port if role == "port" else ocean.config.ssl.third_party
    )
    return resolve_verify_param(ssl_settings)


def resolve_custom_integration_verify(verify_ssl: bool) -> bool | ssl.SSLContext:
    if not verify_ssl:
        logger.warning(
            "integration config verify_ssl=false is deprecated. "
            "Use OCEAN__SSL__THIRD_PARTY__VERIFY=false instead."
        )
        return False

    return resolve_verify_param_for_ocean_role("third_party")
