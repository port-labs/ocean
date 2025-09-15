from typing import Optional, Any, Dict
from dataclasses import dataclass
from sailpoint.exceptions import (
    ThirdPartyAPIError,
    SailPointAuthError,
    SailPointTokenExpiredError,
)
from sailpoint.utils.logging import Logger
from port_ocean.utils.async_http import http_async_client
from port_ocean.utils.async_iterators import stream_async_iterators_tasks
from port_ocean.log.sensetive import sensitive_log_filter

import asyncio


@dataclass
class TokenInfo:
    access_token: str
    expires_at: float
    tenant_id: str
    user_id: Optional[str] = None
    identity_id: Optional[str] = None


@dataclass
class OAuth2Config:
    client_id: str
    client_secret: str
    token_url: str
    scopes: Optional[list[str]] = None
    additional_params: Optional[Dict[str, Any]] = None


class SailPointAuthManager:
    """
    Handles OAuth2 authentication lifecycle for our SailPointClient
    """

    SAILPOINT_DEFAULT_API_VERSION = "v2025"

    def __init__(
        self, oauth_config: OAuth2Config, base_url: str, auth_type: str = "pat"
    ) -> None:
        self._config = oauth_config
        self._token_info: Optional[TokenInfo] = None
        self._token_lock = asyncio.Lock()
        self._auth_type = auth_type
        self._base_url = base_url.rstrip("/")

    @Logger.log_external_api_call
    async def _request_token(self) -> dict[str, Any]:
        raise NotImplementedError
