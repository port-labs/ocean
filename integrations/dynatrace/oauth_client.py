from loguru import logger
from typing import Optional, Any
import time
import httpx
from port_ocean.utils import http_async_client


class OAuthClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        account_id: str,
        token_url: str = "https://sso.dynatrace.com/sso/oauth2/token",
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.account_id = account_id
        self.token_url = token_url
        self.access_token: Optional[str] = None
        self.token_expiry: float = 0
        self.client = http_async_client

    async def _retrieve_token(self) -> None:
        """Retrieve a new bearer token using the correct URL-encoded format."""
        logger.info("Fetching a new OAuth token...")
        try:
            response = await self.client.post(
                self.token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": "account-idm-read iam:users:read iam:groups:read",
                    "resource": f"urn:dtaccount:{self.account_id}",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            token_data = response.json()
            self.access_token = token_data["access_token"]
            # The token expires in 'expires_in' seconds. Set a buffer of 10 seconds regenerate early.
            self.token_expiry = time.time() + token_data.get("expires_in", 300) - 10
            logger.warning(
                f"OAuth token retrieved successfully. Expiring in {self.token_expiry}"
            )
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch OAuth token: {e}")
            raise

    async def _ensure_token(self) -> None:
        """Ensure that a valid access token is available."""
        if not self.access_token or time.time() >= self.token_expiry:
            logger.info("Access token expired or not available. Refreshing...")
            await self._retrieve_token()

    async def _prepare_headers(self) -> None:
        """Update headers with the latest access token."""
        await self._ensure_token()
        self.client.headers.update({"Authorization": f"Bearer {self.access_token}"})

    async def send_request(
        self, method: str, url: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Make a request with updated headers."""
        await self._prepare_headers()
        try:
            response = await self.client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            # If we get a 401 Unauthorized, refresh the token and retry the request
            if e.response.status_code == 401:
                logger.warning(
                    "Token expired or invalid (401). Refreshing token and retrying request..."
                )
                # await self._retrieve_token()
                await self._prepare_headers()
                response = await self.client.request(method, url, **kwargs)
                response.raise_for_status()
                return response.json()
            else:
                logger.error(f"HTTP error during {method} request to {url}: {e}")
                raise
        except httpx.HTTPError as e:
            logger.error(f"HTTP error during {method} request to {url}: {e}")
            raise
