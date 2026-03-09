from typing import Dict, Any, Type
import httpx

from custom.auth.base import AuthHandler
from custom.auth.bearer_token import BearerTokenAuth
from custom.auth.api_key import ApiKeyAuth
from custom.auth.basic import BasicAuth
from custom.auth.no_auth import NoAuth
from custom.auth.custom import CustomAuth

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
) -> AuthHandler:
    """Get the appropriate authentication handler"""
    if auth_type == "custom":
        return CustomAuth(client, config)
    handler_class = AUTH_HANDLERS.get(auth_type, NoAuth)
    return handler_class(client, config)
