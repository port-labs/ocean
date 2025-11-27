import asyncio
import base64
from typing import Optional
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, PrivateAttr
from loguru import logger
import httpx

from auth.abstract_authenticator import AbstractServiceNowAuthenticator
from port_ocean.helpers.retry import RetryConfig
from port_ocean.helpers.async_client import OceanAsyncClient
from port_ocean.context.ocean import ocean


class ServiceNowToken(BaseModel):
    """Model representing a ServiceNow OAuth access token."""

    access_token: str
    expires_in: int
    token_type: str
    _created_at: datetime = PrivateAttr(default_factory=lambda: datetime.now(timezone.utc))
    _time_buffer: timedelta = PrivateAttr(default_factory=lambda: timedelta(minutes=2))

    @property
    def is_expired(self) -> bool:
        expires_at = self._created_at + timedelta(seconds=self.expires_in)
        return datetime.now(timezone.utc) >= (expires_at - self._time_buffer)


class OAuthClientCredentialsAuthenticator(AbstractServiceNowAuthenticator):
    """Authenticator using OAuth 2.0 Client Credentials Grant flow."""

    def __init__(self, servicenow_url: str, client_id: str, client_secret: str):
        self.servicenow_url = servicenow_url.rstrip("/")
        self.token_url = f"{self.servicenow_url}/oauth_token.do"
        self.client_id = client_id
        self.client_secret = client_secret
        self.cached_token: Optional[ServiceNowToken] = None
        self.token_lock = asyncio.Lock()

    @property
    def _http_client(self) -> httpx.AsyncClient:
        retry_config = RetryConfig(
            retry_after_headers=["Retry-After"],
        )
        return OceanAsyncClient(
            retry_config=retry_config,
            timeout=ocean.config.client_timeout,
        )

    async def get_headers(self) -> dict[str, str]:
        token = await self._get_valid_token()
        return {
            "Authorization": f"Bearer {token.access_token}",
            "Content-Type": "application/json",
        }

    async def _get_valid_token(self) -> ServiceNowToken:
        async with self.token_lock:
            if self.cached_token and not self.cached_token.is_expired:
                return self.cached_token

            self.cached_token = await self._fetch_token()
            logger.info("New ServiceNow OAuth token acquired")
            return self.cached_token

    def _get_basic_auth_header(self) -> str:
        """Generate Basic Auth header from client credentials."""
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
        return f"Basic {encoded}"

    async def _fetch_token(self) -> ServiceNowToken:
        try:
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": self._get_basic_auth_header(),
            }
            data = {"grant_type": "client_credentials"}

            response = await self._http_client.post(
                self.token_url,
                data=data,
                headers=headers,
            )
            response.raise_for_status()

            token_data = response.json()
            return ServiceNowToken(
                access_token=token_data["access_token"],
                expires_in=token_data.get("expires_in", 1800),
                token_type=token_data.get("token_type", "Bearer"),
            )
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Failed to fetch OAuth token: HTTP {e.response.status_code} - {e.response.text}"
            )
            raise
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch OAuth token: {e}")
            raise

