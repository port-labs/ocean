import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from httpx import AsyncClient
from loguru import logger
from pydantic import BaseModel, PrivateAttr

from azure_devops.client.auth.base import Authenticator

AZURE_DEVOPS_RESOURCE_ID = "499b84ac-1321-427f-aa17-267ca6975798"
AZURE_DEVOPS_DEFAULT_SCOPE = f"{AZURE_DEVOPS_RESOURCE_ID}/.default"


class EntraIdToken(BaseModel):
    access_token: str
    expires_in: int
    token_type: str = "Bearer"
    _created_at: datetime = PrivateAttr(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    _time_buffer: timedelta = PrivateAttr(default_factory=lambda: timedelta(minutes=2))

    @property
    def is_expired(self) -> bool:
        expires_at = self._created_at + timedelta(seconds=self.expires_in)
        return datetime.now(timezone.utc) >= (expires_at - self._time_buffer)


class ServicePrincipalAuthenticator(Authenticator):
    """Acquires and caches an Entra ID access token via the OAuth 2.0
    client-credentials grant.

    A single instance is shared across every per-org ``AzureDevopsClient`` in
    Service Principal mode — the token is tenant-scoped, not org-scoped, so
    fetching it once per manager avoids N redundant token requests.
    """

    def __init__(self, tenant_id: str, client_id: str, client_secret: str) -> None:
        self._tenant_id = tenant_id
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = (
            f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        )
        self._cached_token: Optional[EntraIdToken] = None
        self._token_lock = asyncio.Lock()

    async def apply(self, client: AsyncClient) -> None:
        token = await self._get_valid_token(client)
        client.auth = None
        client.headers["Authorization"] = f"{token.token_type} {token.access_token}"

    async def _get_valid_token(self, client: AsyncClient) -> EntraIdToken:
        async with self._token_lock:
            if self._cached_token and not self._cached_token.is_expired:
                return self._cached_token
            self._cached_token = await self._fetch_token(client)
            logger.debug(
                "New Entra ID token acquired for Azure DevOps Service Principal"
            )
            return self._cached_token

    async def _fetch_token(self, client: AsyncClient) -> EntraIdToken:
        data = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "scope": AZURE_DEVOPS_DEFAULT_SCOPE,
        }
        try:
            response = await client.post(
                self._token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            body = response.json()
            return EntraIdToken(
                access_token=body["access_token"],
                expires_in=body.get("expires_in", 3600),
                token_type=body.get("token_type", "Bearer"),
            )
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Failed to acquire Entra ID token for Azure DevOps: "
                f"HTTP {exc.response.status_code} - {exc.response.text}"
            )
            raise
        except httpx.HTTPError as exc:
            logger.error(f"Failed to acquire Entra ID token for Azure DevOps: {exc}")
            raise
