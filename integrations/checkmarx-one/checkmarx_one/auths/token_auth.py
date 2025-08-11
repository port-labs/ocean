from typing import Any

import httpx
from loguru import logger

from checkmarx_one.auths.base_auth import BaseCheckmarxAuthenticator
from checkmarx_one.exceptions import CheckmarxAuthenticationError


class TokenAuthenticator(BaseCheckmarxAuthenticator):
    """
    Handles API key authentication for Checkmarx One API.
    Uses refresh token flow with API key as the refresh token.
    """

    def __init__(
        self,
        iam_url: str,
        tenant: str,
        api_key: str | None,
    ):
        """
        Initialize the token authenticator.

        Args:
            iam_url: IAM URL for authentication (e.g., https://iam.checkmarx.net)
            tenant: Tenant name for authentication
            api_key: API key for authentication (used as refresh token)
        """
        super().__init__(iam_url, tenant)
        self.api_key = api_key

    async def _authenticate(self) -> dict[str, Any]:
        """Authenticate using API key (refresh token flow)."""
        logger.debug("Authenticating with API key")

        auth_data = {
            "grant_type": "refresh_token",
            "client_id": "ast-app",
            "refresh_token": self.api_key,
        }

        try:
            response = await self.http_client.post(
                self.auth_url,
                data=auth_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(
                f"API key authentication failed: {e.response.status_code} - {e.response.text}"
            )
            raise CheckmarxAuthenticationError(
                f"API key authentication failed: {e.response.text}"
            )
