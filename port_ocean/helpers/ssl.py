"""
SSL configuration helpers for the ocean framework.
"""

import os
import ssl
from enum import Enum
from typing import Any

import certifi
from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.exceptions.context import PortOceanContextNotFoundError


class SSLClientType(Enum):
    """Type of client to configure SSL for"""

    PORT = "PORT"
    THIRD_PARTY = "THIRD_PARTY"


def _get_ocean_config_value(name: str, default: Any) -> Any:
    try:
        return getattr(ocean.config, name)
    except (AttributeError, PortOceanContextNotFoundError):
        return default


def _create_httpx_default_ssl_context() -> ssl.SSLContext:
    if os.environ.get("SSL_CERT_FILE"):
        return ssl.create_default_context(cafile=os.environ["SSL_CERT_FILE"])
    if os.environ.get("SSL_CERT_DIR"):
        return ssl.create_default_context(capath=os.environ["SSL_CERT_DIR"])
    return ssl.create_default_context(cafile=certifi.where())


def get_ssl_context(
    client_type: SSLClientType = SSLClientType.PORT,
) -> ssl.SSLContext | bool:
    """
    Get SSL context configuration based on ocean settings.

    Args:
        client_type: Type of client to get SSL context for (PORT or THIRD_PARTY)

    Settings for Port client (client_type=PORT):
        OCEAN__PORT_VERIFY_SSL: Enable/disable SSL verification (default: True)
        OCEAN__PORT_DISABLE_STRICT_SSL_VERIFICATION: Disable strict x509 verification introduced in Python 3.13 (default: False)

    Settings for Third Party clients (client_type=THIRD_PARTY):
        OCEAN__THIRD_PARTY_VERIFY_SSL: Enable/disable SSL verification (default: True)
        OCEAN__THIRD_PARTY_DISABLE_STRICT_SSL_VERIFICATION: Disable strict x509 verification introduced in Python 3.13 (default: False)

    Returns:
        SSLContext for custom verification settings, False to disable verification, or True for default verification.
    """

    if client_type == SSLClientType.THIRD_PARTY:
        verify_ssl = _get_ocean_config_value("third_party_verify_ssl", True)
        disable_strict_ssl_verification = _get_ocean_config_value(
            "third_party_disable_strict_ssl_verification",
            False,
        )
    else:
        verify_ssl = _get_ocean_config_value("port_verify_ssl", True)
        disable_strict_ssl_verification = _get_ocean_config_value(
            "port_disable_strict_ssl_verification",
            False,
        )

    client_name = "third party" if client_type == SSLClientType.THIRD_PARTY else "Port"

    if not verify_ssl:
        logger.warning(
            f"SSL certificate verification is disabled for {client_name} client. "
            f"This is not recommended for production use."
        )
        return False

    if disable_strict_ssl_verification:
        logger.warning(
            f"Strict X.509 certificate verification is disabled for {client_name} client. "
            f"This may affect security."
        )
        context = _create_httpx_default_ssl_context()
        # Remove VERIFY_X509_STRICT flag that is set by default starting Python 3.13
        # See: https://docs.python.org/3/library/ssl.html#ssl.create_default_context
        context.verify_flags &= ~ssl.VERIFY_X509_STRICT
        return context

    return True
