import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

from loguru import logger

from port_ocean.identity_propagation.vault.base import TokenRecord
from port_ocean.config.settings import OAuthProviderSettings
from port_ocean.exceptions.identity_propagation import (
    OAuthError,
    OAuthProviderNotConfiguredError,
)
from port_ocean.utils import http_async_client


@dataclass(frozen=True)
class ProviderDefaults:

    authorize_url: str
    token_url: str
    scopes: str
    default_host: str | None = None


def require_provider() -> "OAuth2Provider":
    """Return this process's single registered OAuth provider.

    There is no target-based lookup: one Ocean process hosts exactly one integration, so
    there's exactly one provider to have registered, set once at startup via
    `ocean.register_oauth_provider`. See `context/ocean.py`.
    """
    from port_ocean.context.ocean import (
        ocean,
    )  # deferred: avoid a circular import with context/ocean.py

    provider = ocean.app.oauth_provider
    if provider is None:
        raise OAuthProviderNotConfiguredError(
            "No OAuth provider registered for this integration"
        )
    return provider


class OAuth2Provider:

    def __init__(
        self, target: str, defaults: ProviderDefaults, settings: OAuthProviderSettings
    ) -> None:
        host = (getattr(settings, "host", None) or defaults.default_host or "").rstrip(
            "/"
        )
        placeholders = {
            "host": host,
            "tenant_id": getattr(settings, "tenant_id", "") or "",
        }

        self.target = target
        self._settings = settings
        self._authorize_url = (settings.authorize_url or defaults.authorize_url).format(
            **placeholders
        )
        self._token_url = (settings.token_url or defaults.token_url).format(
            **placeholders
        )
        self._scopes = settings.scopes or defaults.scopes

    def authorization_url(self, redirect_uri: str, state: str) -> str:
        params = {
            "client_id": self._settings.client_id,
            "redirect_uri": redirect_uri,
            "scope": self._scopes,
            "state": state,
            "response_type": "code",
        }
        return f"{self._authorize_url}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> TokenRecord:
        return await self._request_token(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "scope": self._scopes,
            }
        )

    async def refresh(self, refresh_token: str) -> TokenRecord:
        return await self._request_token(
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "scope": self._scopes,
            }
        )

    async def _request_token(self, data: dict[str, str]) -> TokenRecord:
        payload = {
            **data,
            "client_id": self._settings.client_id,
            "client_secret": self._settings.client_secret,
        }
        try:
            response = await http_async_client.post(
                self._token_url,
                data=payload,
                headers={"Accept": "application/json"},
            )
        except Exception as e:
            raise OAuthError(f"Token request to {self.target} failed: {e}") from e

        if response.status_code >= 400:
            raise OAuthError(
                f"Token request to {self.target} returned {response.status_code}"
            )

        try:
            body = response.json()
        except Exception as e:
            raise OAuthError(
                f"Token response from {self.target} was not valid JSON"
            ) from e

        return self._to_record(body)

    def _to_record(self, body: dict[str, Any]) -> TokenRecord:
        access_token = body.get("access_token")
        if not access_token:
            # GitHub answers 200 with an error body, so the status code is not
            # enough to tell success from failure.
            raise OAuthError(
                f"Token response from {self.target} carried no access token"
                f" ({body.get('error', 'unknown error')})"
            )

        expires_in = body.get("expires_in")
        expires_at = int(time.time()) + int(expires_in) if expires_in else None
        if expires_at is None:
            logger.debug(
                "Provider returned no expiry; token will be used until rejected",
                target=self.target,
            )

        return TokenRecord(
            access_token=access_token,
            refresh_token=body.get("refresh_token"),
            expires_at=expires_at,
        )
