import asyncio
import base64
import time
from typing import Optional
from httpx import AsyncClient
from loguru import logger
from helpers.exceptions import MissingIntegrationCredentialException

DEFAULT_TOKEN_EXPIRY_SECONDS = 3600
TOKEN_EXPIRY_BUFFER_SECONDS = 60
AUTH_TOKEN_ENDPOINT = "api/oauth/token"


class AikidoAuth:
    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        http_client: AsyncClient,
    ):
        if not client_id or not client_secret:
            raise MissingIntegrationCredentialException(
                "Aikido client ID and secret must be provided."
            )
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0
        self.http_client = http_client
        self._lock = asyncio.Lock()

    async def get_token(self) -> str | None:
        if self._access_token and time.time() < self._token_expiry:
            return self._access_token
        async with self._lock:
            if self._access_token and time.time() < self._token_expiry:
                return self._access_token

            await self._generate_oauth_token()
            return self._access_token

    async def _generate_oauth_token(self) -> None:
        try:
            auth_string = f"{self.client_id}:{self.client_secret}"
            b64_auth = base64.b64encode(auth_string.encode("ascii")).decode("ascii")

            headers = {
                "Authorization": f"Basic {b64_auth}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
            data = {"grant_type": "client_credentials"}

            logger.info("Generating OAuth token from Aikido API")
            response = await self.http_client.post(
                f"{self.base_url}/{AUTH_TOKEN_ENDPOINT}",
                headers=headers,
                json=data,
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
            logger.info("OAuth token generated successfully")
        except Exception as e:
            logger.error(f"OAuth token generation failed: {e}")
            raise
