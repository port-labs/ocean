import asyncio
import time
from typing import Optional

import httpx
from loguru import logger
from port_ocean.utils import http_async_client

from mend.exceptions import MendAuthenticationError


class MendAuthenticator:
    def __init__(
        self,
        base_url: str,
        email: str,
        user_key: str,
        org_uuid: str,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.user_key = user_key
        self.org_uuid = org_uuid
        self._jwt_token: Optional[str] = None
        self._token_expires_at: Optional[float] = None
        self._refresh_lock = asyncio.Lock()

    @property
    def is_token_expired(self) -> bool:
        if not self._token_expires_at:
            return True
        return time.time() >= (self._token_expires_at - 60)

    async def invalidate_token(self) -> None:
        """Clear the in-memory token so the next request re-authenticates."""
        self._jwt_token = None
        self._token_expires_at = None
        logger.info(f"Mend token invalidated for org {self.org_uuid}")

    async def _fetch_refresh_token(self) -> str:
        login_url = f"{self.base_url}/api/v3.0/login"
        try:
            response = await http_async_client.post(
                login_url,
                json={"email": self.email, "userKey": self.user_key},
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            data: dict[str, object] = response.json()
            resp = data.get("response", {})
            if not isinstance(resp, dict):
                raise MendAuthenticationError("Unexpected login response format")
            return str(resp["refreshToken"])
        except httpx.HTTPStatusError as e:
            raise MendAuthenticationError(
                f"Mend login failed ({e.response.status_code}): {e.response.text}"
            ) from e

    async def _fetch_jwt_token(self, refresh_token: str) -> tuple[str, int]:
        token_url = f"{self.base_url}/api/v3.0/login/accessToken"
        try:
            response = await http_async_client.post(
                token_url,
                params={"orgUuid": self.org_uuid},
                headers={
                    "Content-Type": "application/json",
                    "wss-refresh-token": refresh_token,
                },
            )
            response.raise_for_status()
            data: dict[str, object] = response.json()
            resp = data.get("response", {})
            if not isinstance(resp, dict):
                raise MendAuthenticationError("Unexpected accessToken response format")
            jwt_token = str(resp["jwtToken"])
            token_ttl = int(resp.get("tokenTTL", 3600))
            return jwt_token, token_ttl
        except httpx.HTTPStatusError as e:
            raise MendAuthenticationError(
                f"Mend accessToken fetch failed ({e.response.status_code}): {e.response.text}"
            ) from e

    async def _authenticate(self) -> None:
        logger.info("Authenticating with Mend — step 1: login")
        refresh_token = await self._fetch_refresh_token()
        logger.info("Mend step 1 succeeded — step 2: fetching JWT token")
        jwt_token, token_ttl = await self._fetch_jwt_token(refresh_token)
        self._jwt_token = jwt_token
        self._token_expires_at = time.time() + token_ttl
        logger.info(f"Mend authentication succeeded, token TTL: {token_ttl} ms")

    async def _get_jwt_token(self) -> str:
        if not self._jwt_token or self.is_token_expired:
            async with self._refresh_lock:
                if self._jwt_token and not self.is_token_expired:
                    return self._jwt_token
                await self._authenticate()

        if not self._jwt_token:
            raise MendAuthenticationError("Failed to obtain JWT token")
        return self._jwt_token

    async def get_auth_headers(self) -> dict[str, str]:
        jwt_token = await self._get_jwt_token()
        return {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json",
        }
