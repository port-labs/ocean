import time
from abc import ABC, abstractmethod
from typing import Any, Optional

import httpx
from loguru import logger
from port_ocean.utils import http_async_client

from exceptions import CheckmarxAuthenticationError


class BaseCheckmarxAuthenticator(ABC):
    """
    Base class for Checkmarx One authentication.
    Handles common token management and HTTP client setup.
    """

    def __init__(
        self,
        iam_url: str,
        tenant: str,
    ):
        """
        Initialize the base authenticator.

        Args:
            iam_url: IAM URL for authentication (e.g., https://iam.checkmarx.net)
            tenant: Tenant name for authentication
        """
        self.iam_url = iam_url.rstrip("/")
        self.tenant = tenant

        # HTTP client setup
        self.http_client = http_async_client
        self.http_client.timeout = httpx.Timeout(30)

        # Token management
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expires_at: Optional[float] = None

    @property
    def auth_url(self) -> str:
        """Get the authentication URL for the tenant."""
        return f"{self.iam_url}/auth/realms/{self.tenant}/protocol/openid-connect/token"

    @property
    def is_token_expired(self) -> bool:
        """Check if the current access token is expired."""
        if not self._token_expires_at:
            return True
        # Add 60 second buffer for token refresh
        return time.time() >= (self._token_expires_at - 60)

    @abstractmethod
    async def _authenticate(self) -> dict[str, Any]:
        """Authenticate and return token response. Must be implemented by subclasses."""
        pass

    async def _refresh_access_token(self) -> None:
        """Refresh the access token using the appropriate method."""
        try:
            token_response = await self._authenticate()

            self._access_token = token_response["access_token"]
            self._refresh_token = token_response.get("refresh_token")

            # Token expires in seconds, store absolute time
            expires_in = token_response.get("expires_in", 1800)  # Default 30 minutes
            self._token_expires_at = time.time() + expires_in

            logger.info(
                f"Successfully refreshed access token, expires in {expires_in} seconds"
            )

        except Exception as e:
            logger.error(f"Failed to refresh access token: {str(e)}")
            raise CheckmarxAuthenticationError(f"Token refresh failed: {str(e)}")

    async def _get_access_token(self) -> str | None:
        """Get a valid access token, refreshing if necessary."""
        if not self._access_token or self.is_token_expired:
            await self._refresh_access_token()

        return self._access_token

    async def get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers for API requests."""
        access_token = await self._get_access_token()
        if access_token is None:
            raise CheckmarxAuthenticationError("Failed to obtain access token")
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def refresh_token(self) -> None:
        """Force refresh the access token."""
        await self._refresh_access_token()
