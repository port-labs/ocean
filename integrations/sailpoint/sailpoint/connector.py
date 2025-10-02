from typing import Optional, Any, Dict
from dataclasses import dataclass
from sailpoint.exceptions import (
    SailPointAuthError,
)
from sailpoint.utils.logging import Logger
from port_ocean.utils.async_http import http_async_client
import time

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
        self._http_client = http_async_client
        self._token_lock = asyncio.Lock()
        self._auth_type = auth_type
        self._base_url = base_url.rstrip("/")

        if auth_type not in ("pat", "oauth2"):
            raise ValueError("auth_type must be either 'pat' or 'oauth2'")

        if auth_type == "pat" and not self._config.client_secret:
            raise ValueError("For PAT auth, client_secret (the PAT) must be provided")

    def _is_token_expired(self) -> bool:
        if not self._token_info:
            return True
        return self._token_info.expires_at <= time.time()

    @Logger.log_external_api_call
    async def get_valid_token(self) -> TokenInfo:
        """
        Returns a valid access token, refreshing it if necessary (expired or missing)

        Supports both PAT and OAuth2 authentication methods
        """
        async with self._token_lock:
            # check if we already have a valid token
            if self._token_info and not self._is_token_expired():
                return self._token_info

            if self._auth_type == "pat":
                INF_EXPIRY_TIME = float("inf")  # PAT does not expire, uneless revoked
                self._token_info = TokenInfo(
                    access_token=self._config.client_secret,
                    expires_at=INF_EXPIRY_TIME,
                    tenant_id=self._config.additional_params.get("tenant_id", "n/a")
                    if self._config.additional_params
                    else "n/a",
                )
                return self._token_info

            if self._auth_type == "oauth2":
                async with self._http_client as client:
                    resp = await client.post(
                        self._config.token_url,
                        data={
                            "grant_type": "client_credentials",
                            "client_id": self._config.client_id,
                            "client_secret": self._config.client_secret,
                            "scope": " ".join(self._config.scopes or []),
                            **(self._config.additional_params or {}),
                        },
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                    )
                    if resp.status_code != 200:
                        raise SailPointAuthError(
                            f"Failed to obtain access token: {resp.status_code} {resp.text}"
                        )

                    payload = resp.json()
                    now = time.time()
                    self._token_info = TokenInfo(
                        access_token=payload["access_token"],
                        expires_at=now + payload.get("expires_in", 3600),
                        tenant_id=self._config.additional_params.get(
                            "tenant_id", "unknown"
                        )
                        if self._config.additional_params
                        else "unknown",
                    )
                    return self._token_info
            raise ValueError("Invalid auth_type, must be either 'pat' or 'oauth2'")
