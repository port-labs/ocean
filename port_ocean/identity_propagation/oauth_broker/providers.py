import time
from typing import Any
from urllib.parse import urlencode

from loguru import logger

from port_ocean.identity_propagation.vault.base import TokenRecord
from port_ocean.exceptions.identity_propagation import (
    OAuthError,
    OAuthProviderNotConfiguredError,
)
from port_ocean.utils import http_async_client


def require_provider() -> "OAuth2Provider":
    """Return this process's single registered OAuth provider.

    There is no target-based lookup: one Ocean process hosts exactly one integration, so
    there's exactly one provider to have registered, set once at startup via
    ``ocean.register_oauth_provider``.  See ``context/ocean.py``.
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
    """Generic OAuth 2.0 provider for identity-propagation token exchange.

    Core owns this class but knows nothing about any specific downstream
    provider (GitHub, GitLab, Azure DevOps, ...).  Integrations construct
    an instance with fully-resolved URLs and credentials, then register it
    via ``ocean.register_oauth_provider(provider)``.
    """

    def __init__(
        self,
        *,
        target: str,
        authorize_url: str,
        token_url: str,
        client_id: str,
        client_secret: str,
        scopes: str,
    ) -> None:
        self.target = target
        self._authorize_url = authorize_url
        self._token_url = token_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._scopes = scopes

    def authorization_url(self, redirect_uri: str, state: str) -> str:
        params = {
            "client_id": self._client_id,
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
            "client_id": self._client_id,
            "client_secret": self._client_secret,
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
            # Some providers (e.g. GitHub) answer 200 with an error body instead
            # of a 4xx status code, so the status alone cannot distinguish success
            # from failure.
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
