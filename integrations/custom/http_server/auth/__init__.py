"""
Authentication handlers for HTTP Server integration.

Provides various authentication strategies using the handler pattern.
"""

from typing import Dict, Any, Optional
from typing_extensions import Type
import httpx

from http_server.auth.base import AuthHandler
from http_server.auth.simple import (
    BearerTokenAuth,
    ApiKeyAuth,
    BasicAuth,
    NoAuth,
)
from http_server.auth.custom_auth import CustomAuth
from http_server.overrides import CustomAuthRequestConfig, CustomAuthResponseConfig

__all__ = [
    "AuthHandler",
    "BearerTokenAuth",
    "ApiKeyAuth",
    "BasicAuth",
    "NoAuth",
    "CustomAuth",
    "AUTH_HANDLERS",
    "get_auth_handler",
]

# Registry of available auth handlers
AUTH_HANDLERS: Dict[str, Type[AuthHandler]] = {
    "bearer_token": BearerTokenAuth,
    "api_key": ApiKeyAuth,
    "basic": BasicAuth,
    "none": NoAuth,
}


def get_auth_handler(
    auth_type: str,
    client: httpx.AsyncClient,
    config: Dict[str, Any],
    custom_auth_request: Optional[CustomAuthRequestConfig] = None,
    custom_auth_response: Optional[CustomAuthResponseConfig] = None,
) -> AuthHandler:
    """Get the appropriate authentication handler"""
    if auth_type == "custom":
        return CustomAuth(client, config, custom_auth_request, custom_auth_response)
    handler_class = AUTH_HANDLERS.get(auth_type, NoAuth)
    return handler_class(client, config)
