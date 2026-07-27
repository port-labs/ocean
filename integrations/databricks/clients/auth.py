import asyncio
import base64
import time
from abc import ABC, abstractmethod
from typing import Optional

import httpx
from loguru import logger
from port_ocean.exceptions.base import BaseOceanException

DEFAULT_TOKEN_EXPIRY_SECONDS = 3600
TOKEN_EXPIRY_BUFFER_SECONDS = 60
OAUTH_TOKEN_ENDPOINT = "oidc/v1/token"
OAUTH_SCOPE = "all-apis"


class MissingIntegrationCredentialException(BaseOceanException):
    pass


class DatabricksAuthenticator(ABC):
    @abstractmethod
    async def get_auth_header(self) -> dict[str, str]: ...


class TokenAuthenticator(DatabricksAuthenticator):
    """Authenticates using a static Databricks Personal Access Token (PAT)."""

    def __init__(self, token: str) -> None:
        if not token:
            raise MissingIntegrationCredentialException(
                "A Databricks personal access token must be provided."
            )
        self._token = token

    async def get_auth_header(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}


class OAuthM2MAuthenticator(DatabricksAuthenticator):
    """Authenticates using Databricks OAuth machine-to-machine (service principal) auth.

    Caches the access token and refreshes it shortly before it expires, guarding the
    refresh with an asyncio.Lock so concurrent callers don't trigger duplicate token
    requests.
    """

    def __init__(
        self,
        workspace_url: str,
        client_id: str,
        client_secret: str,
        http_client: httpx.AsyncClient,
    ) -> None:
        if not client_id or not client_secret:
            raise MissingIntegrationCredentialException(
                "Databricks client ID and client secret must be provided."
            )
        self.workspace_url = workspace_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.http_client = http_client
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0
        self._lock = asyncio.Lock()

    async def get_auth_header(self) -> dict[str, str]:
        token = await self._get_token()
        return {"Authorization": f"Bearer {token}"}

    async def _get_token(self) -> str:
        if self._access_token and time.time() < self._token_expiry:
            return self._access_token

        async with self._lock:
            if self._access_token and time.time() < self._token_expiry:
                return self._access_token

            await self._generate_oauth_token()

        if not self._access_token:
            raise MissingIntegrationCredentialException(
                "Failed to generate a Databricks OAuth access token."
            )
        return self._access_token

    async def _generate_oauth_token(self) -> None:
        try:
            auth_string = f"{self.client_id}:{self.client_secret}"
            b64_auth = base64.b64encode(auth_string.encode("ascii")).decode("ascii")

            headers = {
                "Authorization": f"Basic {b64_auth}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            }
            data = {"grant_type": "client_credentials", "scope": OAUTH_SCOPE}

            logger.info("Generating Databricks OAuth M2M token")
            response = await self.http_client.post(
                f"{self.workspace_url}/{OAUTH_TOKEN_ENDPOINT}",
                headers=headers,
                data=data,
                timeout=30,
            )
            response.raise_for_status()

            token_data = response.json()
            self._access_token = token_data["access_token"]
            self._token_expiry = (
                time.time()
                + token_data.get("expires_in", DEFAULT_TOKEN_EXPIRY_SECONDS)
                - TOKEN_EXPIRY_BUFFER_SECONDS
            )
            logger.info("Databricks OAuth M2M token generated successfully")
        except Exception as e:
            logger.error(f"Databricks OAuth M2M token generation failed: {e}")
            raise


def build_authenticator(
    workspace_url: str,
    token: Optional[str],
    client_id: Optional[str],
    client_secret: Optional[str],
    http_client: httpx.AsyncClient,
) -> DatabricksAuthenticator:
    """Pick the authenticator based on which credentials are configured.

    A static PAT (`token`) takes precedence over OAuth M2M service-principal
    credentials (`client_id` + `client_secret`) if both happen to be set.
    """
    if token:
        return TokenAuthenticator(token)
    if client_id and client_secret:
        return OAuthM2MAuthenticator(
            workspace_url, client_id, client_secret, http_client
        )

    raise MissingIntegrationCredentialException(
        "Either 'token' or both 'clientId' and 'clientSecret' must be configured "
        "for the Databricks integration."
    )
