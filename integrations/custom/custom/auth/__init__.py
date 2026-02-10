"""
Authentication handlers for HTTP Server integration.

Provides various authentication strategies using the handler pattern.
"""

from custom.auth.factory import get_auth_handler

__all__ = [
    "CustomAuth",
    "BearerTokenAuth",
    "ApiKeyAuth",
    "BasicAuth",
    "NoAuth",
    "get_auth_handler",
]
