import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

from loguru import logger

from port_ocean.identity_propagation.vault.base import TokenRecord
from port_ocean.config.settings import OAuthProviderSettings
from port_ocean.exceptions.identity_propagation import OAuthError
from port_ocean.utils import http_async_client

GITHUB = "github"
GITLAB = "gitlab"
AZURE_DEVOPS = "azure-devops"

# Azure DevOps' resource id in Entra ID, the same for every tenant.
ADO_RESOURCE_ID = "499b84ac-1321-427f-aa17-267ca6975798"


@dataclass(frozen=True)
class ProviderDefaults:

    authorize_url: str
    token_url: str
    scopes: str
    default_host: str | None = None


PROVIDER_DEFAULTS: dict[str, ProviderDefaults] = {
    GITHUB: ProviderDefaults(
        authorize_url="https://github.com/login/oauth/authorize",
        token_url="https://github.com/login/oauth/access_token",
        # GitHub App user-to-server tokens: access is controlled by the App
        # Manifest permissions, not by OAuth scopes. Default is empty; set
        # OAUTH_GITHUB_SCOPE only if using a classic OAuth App instead.
        scopes="",
    ),
    GITLAB: ProviderDefaults(
        authorize_url="{host}/oauth/authorize",
        token_url="{host}/oauth/token",
        scopes="api",
        default_host="https://gitlab.com",
    ),
    AZURE_DEVOPS: ProviderDefaults(
        # offline_access is what makes Entra ID issue a refresh token; without it
        # an Azure DevOps user re-authenticates roughly hourly.
        authorize_url="https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize",
        token_url="https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
        scopes=f"{ADO_RESOURCE_ID}/user_impersonation offline_access",
    ),
}


class OAuth2Provider:

    def __init__(self, target: str, settings: OAuthProviderSettings) -> None:
        defaults = PROVIDER_DEFAULTS[target]
        host = (getattr(settings, "host", None) or defaults.default_host or "").rstrip("/")
        placeholders = {"host": host, "tenant_id": getattr(settings, "tenant_id", "") or ""}

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
