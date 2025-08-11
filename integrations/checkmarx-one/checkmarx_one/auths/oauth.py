from typing import Any

import httpx
from loguru import logger

from checkmarx_one.auths.base_auth import BaseCheckmarxAuthenticator
from checkmarx_one.exceptions import CheckmarxAuthenticationError


class OAuthAuthenticator(BaseCheckmarxAuthenticator):
    """
    Handles OAuth client credentials authentication for Checkmarx One API.
    Uses client credentials grant type.
    """

    def __init__(
        self,
        iam_url: str,
        tenant: str,
        client_id: str | None,
        client_secret: str | None,
    ):
        """
        Initialize the OAuth authenticator.

        Args:
            iam_url: IAM URL for authentication (e.g., https://iam.checkmarx.net)
            tenant: Tenant name for authentication
            client_id: OAuth client ID
            client_secret: OAuth client secret
        """
        super().__init__(iam_url, tenant)
        self.client_id = client_id
        self.client_secret = client_secret

    async def _authenticate(self) -> dict[str, Any]:
        """Authenticate using OAuth client credentials."""
        logger.debug(f"Authenticating with OAuth client: {self.client_id}")

        auth_data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
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
                f"OAuth authentication failed: {e.response.status_code} - {e.response.text}"
            )
            raise CheckmarxAuthenticationError(
                f"OAuth authentication failed: {e.response.text}"
            )
