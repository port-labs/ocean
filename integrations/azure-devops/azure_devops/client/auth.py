import asyncio
import base64
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

import httpx
from loguru import logger


ADO_SCOPE = "499b84ac-1321-427f-aa17-267ca6975798/.default"


class AuthProvider(Protocol):
    auth_description: str

    async def get_auth_headers(self) -> dict[str, str]: ...


class PatAuthProvider:
    auth_description = "PAT (Personal Access Token)"

    def __init__(self, pat: str) -> None:
        encoded = base64.b64encode(f":{pat}".encode()).decode()
        self._headers = {"Authorization": f"Basic {encoded}"}

    async def get_auth_headers(self) -> dict[str, str]:
        return self._headers


class ServicePrincipalTokenManager:
    REFRESH_MARGIN = timedelta(minutes=5)
    AZURE_AD_TOKEN_URL = (
        "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    )

    def __init__(
        self, client_id: str, client_secret: str, tenant_id: str
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._tenant_id = tenant_id
        self._token: str | None = None
        self._expires_at: datetime | None = None
        self._lock = asyncio.Lock()

    async def get_token(self) -> str:
        async with self._lock:
            if (
                self._token
                and self._expires_at
                and (self._expires_at - datetime.now(timezone.utc))
                > self.REFRESH_MARGIN
            ):
                return self._token
            self._token, self._expires_at = await self._fetch_token()
            logger.info("Acquired new Azure AD token for Service Principal")
            return self._token

    async def _fetch_token(self) -> tuple[str, datetime]:
        url = self.AZURE_AD_TOKEN_URL.format(tenant=self._tenant_id)
        data = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "scope": ADO_SCOPE,
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                response.raise_for_status()
                token_data = response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Failed to fetch Azure AD token: HTTP {e.response.status_code} - {e.response.text}"
            )
            raise
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch Azure AD token: {e}")
            raise

        access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 3600)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        return access_token, expires_at


class ServicePrincipalAuthProvider:
    auth_description = "Service Principal credentials"

    def __init__(self, token_manager: ServicePrincipalTokenManager) -> None:
        self._token_manager = token_manager

    async def get_auth_headers(self) -> dict[str, str]:
        token = await self._token_manager.get_token()
        return {"Authorization": f"Bearer {token}"}


_token_manager: ServicePrincipalTokenManager | None = None


def build_auth_provider(config: dict[str, Any]) -> AuthProvider:
    has_pat = bool(config.get("personal_access_token"))
    has_sp = bool(config.get("client_id"))

    if has_pat and has_sp:
        raise ValueError(
            "Both PAT and Service Principal credentials are configured. "
            "Use one authentication method, not both."
        )

    if has_sp:
        for field in ("client_id", "client_secret", "tenant_id"):
            if not config.get(field):
                raise ValueError(
                    f"Service Principal auth requires '{field}'. "
                    "Provide clientId, clientSecret, and tenantId."
                )
        client_id: str = config["client_id"]
        client_secret: str = config["client_secret"]
        tenant_id: str = config["tenant_id"]
        global _token_manager
        if _token_manager is None:
            _token_manager = ServicePrincipalTokenManager(
                client_id, client_secret, tenant_id
            )
        return ServicePrincipalAuthProvider(_token_manager)

    if has_pat:
        pat: str = config["personal_access_token"]
        return PatAuthProvider(pat)

    raise ValueError(
        "No authentication configured. Provide either "
        "personalAccessToken (PAT) or Service Principal credentials "
        "(clientId, clientSecret, tenantId)."
    )
